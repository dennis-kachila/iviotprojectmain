"""
IoT-Based IV Fluid Monitoring System
Drop Counting, Prescription Control, and Bubble Detection

Modified Design:
- Drop IR sensor for drop counting (single source of truth)
- Dual bubble detection (IR + Slot module confirmation)
- 4x3 Keypad for prescription input
- SMS alerts via Africa's Talking (ONLINE mode)
- Local-only mode with graceful degradation
"""

import json
import gc
import utime
from machine import Pin, PWM, I2C

try:
    import network
    import urequests
except ImportError:
    network = None
    urequests = None

# Local modules
from i2c_lcd import I2cLcd
from logger import info, warning, error, critical
from keypad import Keypad, KeypadInput
from sensors import DropSensor, BubbleDetector
import config

# Secrets file
SECRETS_JSON = "secrets.json"

# WiFi/SMS credentials (loaded from secrets.json)
WIFI_SSID = ""
WIFI_PASSWORD = ""
SMS_USERNAME = ""
SMS_RECIPIENTS = []
SMS_API_KEY = ""


# ============================================================================
# DEBOUNCED BUTTON CLASS
# ============================================================================

class DebouncedButton:
    """Hardware button with software debouncing"""
    def __init__(self, pin, debounce_ms=30):
        self.pin = Pin(pin, Pin.IN, Pin.PULL_DOWN)
        self.debounce_ms = debounce_ms
        self._last_state = 0
        self._stable_state = 0
        self._last_change = utime.ticks_ms()

    def read(self):
        return self.pin.value()

    def pressed(self):
        now = utime.ticks_ms()
        state = self.read()
        if state != self._last_state:
            self._last_state = state
            self._last_change = now
        if utime.ticks_diff(now, self._last_change) > self.debounce_ms:
            if state != self._stable_state:
                self._stable_state = state
                if state == 1:  # Rising edge
                    return True
        return False


# ============================================================================
# BUZZER CLASS
# ============================================================================

class Buzzer:
    """PWM buzzer with multiple alarm patterns"""
    MODE_OFF = "off"
    MODE_LOW = "low"
    MODE_COMPLETE = "complete"
    MODE_FAULT = "fault"
    MODE_BUBBLE = "bubble"
    MODE_NO_FLOW = "no_flow"

    def __init__(self, pin, freq=2000):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(freq)
        self.mode = self.MODE_OFF
        self._last_toggle = utime.ticks_ms()
        self._state = 0

    def set_mode(self, mode):
        if mode != self.mode:
            self.mode = mode
            self._state = 0
            self._last_toggle = utime.ticks_ms()

    def update(self):
        """Update buzzer state based on current mode"""
        now = utime.ticks_ms()
        
        if self.mode == self.MODE_OFF:
            self.pwm.duty_u16(0)
            return
        
        # Continuous modes
        if self.mode in [self.MODE_COMPLETE, self.MODE_FAULT]:
            self.pwm.duty_u16(config.BUZZER_ON_DUTY * 64)  # Convert to 16-bit
            return
        
        # Pulsing modes
        intervals = {
            self.MODE_LOW: config.BUZZER_INTERVAL_LOW,
            self.MODE_BUBBLE: config.BUZZER_INTERVAL_BUBBLE,
            self.MODE_NO_FLOW: config.BUZZER_INTERVAL_NO_FLOW,
        }
        
        interval = intervals.get(self.mode, 200)
        
        if utime.ticks_diff(now, self._last_toggle) >= interval:
            self._state = 1 - self._state
            self._last_toggle = now
            if self._state:
                self.pwm.duty_u16(config.BUZZER_ON_DUTY * 64)
            else:
                self.pwm.duty_u16(0)


# ============================================================================
# SMS SENDER CLASS
# ============================================================================

class SmsSender:
    """SMS notification via Africa's Talking API"""
    def __init__(self, username, api_key, recipients):
        self.username = username
        self.api_key = api_key
        self.recipients = recipients
        self.connected = False
        
        if not network or not urequests:
            info("Network modules not available - LOCAL mode only")
            self.connected = False

    def connect_wifi(self, ssid, password, timeout_s=15):
        """Connect to WiFi"""
        if not network:
            warning("Network module not available")
            return False
        
        try:
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
            
            if wlan.isconnected():
                info("WiFi already connected")
                self.connected = True
                return True
            
            info(f"Connecting to WiFi: {ssid}")
            wlan.connect(ssid, password)
            
            start = utime.time()
            while not wlan.isconnected():
                if utime.time() - start > timeout_s:
                    warning("WiFi connection timeout")
                    return False
                utime.sleep(0.5)
            
            info(f"WiFi connected: {wlan.ifconfig()[0]}")
            self.connected = True
            return True
            
        except Exception as e:
            error(f"WiFi connection error: {e}")
            return False

    def test_internet(self, timeout_s=5):
        """Test internet connectivity via Africa's Talking API"""
        if not urequests:
            return False
        
        try:
            response = urequests.get(
                config.SMS_API_ENDPOINT,
                timeout=timeout_s
            )
            response.close()
            return True
        except:
            return False

    def send(self, message):
        """Send SMS to all recipients"""
        if not self.connected or not urequests:
            return False
        
        if not self.recipients:
            return False
        
        try:
            headers = {
                "apiKey": self.api_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            
            for recipient in self.recipients:
                data = f"username={self.username}&to={recipient}&message={message}"
                response = urequests.post(
                    config.SMS_API_ENDPOINT,
                    headers=headers,
                    data=data,
                    timeout=5
                )
                response.close()
            
            info(f"SMS sent: {message}")
            return True
            
        except Exception as e:
            error(f"SMS send error: {e}")
            return False


# ============================================================================
# PRESCRIPTION DATA CLASS
# ============================================================================

class Prescription:
    """Stores and validates prescription data"""
    def __init__(self):
        self.target_volume_ml = None
        self.duration_minutes = None
        self.drip_factor_gtt_ml = config.DEFAULT_DRIP_FACTOR
        self.gtt_per_min_target = None
        self.ml_per_hr_prescribed = None
    
    def set_volume(self, volume_ml):
        """Set target volume with validation"""
        if config.MIN_VOLUME_ML <= volume_ml <= config.MAX_VOLUME_ML:
            self.target_volume_ml = volume_ml
            self._recalculate()
            return True
        return False
    
    def set_duration(self, duration_min):
        """Set duration with validation"""
        if config.MIN_DURATION_MIN <= duration_min <= config.MAX_DURATION_MIN:
            self.duration_minutes = duration_min
            self._recalculate()
            return True
        return False
    
    def set_drip_factor(self, drip_factor):
        """Set drip factor"""
        self.drip_factor_gtt_ml = drip_factor
        self._recalculate()
        return True
    
    def _recalculate(self):
        """Recalculate derived values"""
        if self.target_volume_ml and self.duration_minutes:
            # mL/hr = (V_target / T_minutes) * 60
            self.ml_per_hr_prescribed = (self.target_volume_ml / self.duration_minutes) * 60
            
            # gtt/min = (V_target * drip_factor) / T_minutes
            self.gtt_per_min_target = (self.target_volume_ml * self.drip_factor_gtt_ml) / self.duration_minutes
    
    def is_complete(self):
        """Check if prescription is fully entered"""
        return self.target_volume_ml is not None and self.duration_minutes is not None
    
    def reset(self):
        """Reset all prescription data"""
        self.target_volume_ml = None
        self.duration_minutes = None
        self.drip_factor_gtt_ml = config.DEFAULT_DRIP_FACTOR
        self.gtt_per_min_target = None
        self.ml_per_hr_prescribed = None


# ============================================================================
# MONITORING STATE CLASS
# ============================================================================

class MonitoringState:
    """Tracks monitoring state and metrics"""
    def __init__(self, prescription):
        self.prescription = prescription
        self.start_time = None
        self.delivered_ml = 0
        self.remaining_ml = 0
        self.percent_delivered = 0
        self.gtt_per_min_measured = 0
        self.ml_per_hr_measured = 0
        self.eta_hours = None
        
        # Milestone flags
        self.milestone_flags = {0: False, 25: False, 50: False, 100: False}
        self.low_volume_sent = False
        self.bubble_sent = False
        self.no_flow_sent = False
        self.time_elapsed_sent = False
    
    def start_monitoring(self):
        """Start monitoring session"""
        self.start_time = utime.time()
        self.delivered_ml = 0
        self.percent_delivered = 0
    
    def update_from_drops(self, total_drops, drops_per_min):
        """Update metrics from drop sensor"""
        drip_factor = self.prescription.drip_factor_gtt_ml
        
        # Calculate delivered volume
        self.delivered_ml = total_drops / drip_factor
        
        # Calculate remaining volume
        self.remaining_ml = max(0, self.prescription.target_volume_ml - self.delivered_ml)
        
        # Calculate percentage
        if self.prescription.target_volume_ml > 0:
            self.percent_delivered = min(100, (self.delivered_ml / self.prescription.target_volume_ml) * 100)
        
        # Calculate measured flow rate
        self.gtt_per_min_measured = drops_per_min
        if drip_factor > 0:
            self.ml_per_hr_measured = (drops_per_min * 60) / drip_factor
        
        # Calculate ETA
        if self.ml_per_hr_measured > 0:
            self.eta_hours = self.remaining_ml / self.ml_per_hr_measured
        else:
            self.eta_hours = None
    
    def get_elapsed_time_seconds(self):
        """Get elapsed time since monitoring started"""
        if self.start_time is None:
            return 0
        return utime.time() - self.start_time
    
    def is_time_elapsed(self):
        """Check if prescribed time has elapsed"""
        if self.start_time is None:
            return False
        elapsed = self.get_elapsed_time_seconds()
        return elapsed >= (self.prescription.duration_minutes * 60)
    
    def is_volume_complete(self):
        """Check if target volume delivered"""
        return self.delivered_ml >= self.prescription.target_volume_ml
    
    def check_milestone(self, percent):
        """Check and mark milestone"""
        if percent in self.milestone_flags:
            if self.percent_delivered >= percent and not self.milestone_flags[percent]:
                self.milestone_flags[percent] = True
                return True
        return False
    
    def reset_counters(self):
        """Reset counters only (keep prescription)"""
        self.start_time = utime.time()
        self.delivered_ml = 0
        self.remaining_ml = self.prescription.target_volume_ml
        self.percent_delivered = 0
        self.milestone_flags = {0: False, 25: False, 50: False, 100: False}
        self.low_volume_sent = False
        self.bubble_sent = False
        self.no_flow_sent = False
        self.time_elapsed_sent = False


# ============================================================================
# LCD HELPER FUNCTIONS
# ============================================================================

def lcd_line(lcd, line, text):
    """Display text on specific LCD line"""
    lcd.move_to(0, line)
    lcd.putstr(text.ljust(config.LCD_COLS))


def update_leds(led_red, led_yellow, led_green, remaining_ml):
    """Update LED status based on remaining volume"""
    if remaining_ml < config.LOW_VOLUME_THRESHOLD_ML:
        led_red.on()
        led_yellow.off()
        led_green.off()
    elif remaining_ml < config.WARNING_VOLUME_THRESHOLD_ML:
        led_red.off()
        led_yellow.on()
        led_green.off()
    else:
        led_red.off()
        led_yellow.off()
        led_green.on()


def display_prescription_input(lcd, prompt, buffer):
    """Display prescription input screen"""
    lcd.clear()
    lcd_line(lcd, 0, "IV PRESCRIPTION")
    lcd_line(lcd, 1, prompt)
    lcd_line(lcd, 2, f"Input: {buffer}")
    lcd_line(lcd, 3, "#=OK *=Back/Default")


def display_monitoring(lcd, state):
    """Display monitoring screen"""
    # Line 0: Volume delivered/total
    lcd_line(lcd, 0, f"VOL {int(state.delivered_ml):03d}/{int(state.prescription.target_volume_ml):03d} mL")
    
    # Line 1: Percentage and remaining
    lcd_line(lcd, 1, f"% {int(state.percent_delivered):02d}  Rem {int(state.remaining_ml):03d}mL")
    
    # Line 2: Current rate
    rate_text = f"Rate {int(state.gtt_per_min_measured):02d}gtt {int(state.ml_per_hr_measured):02d}mLh"
    lcd_line(lcd, 2, rate_text)
    
    # Line 3: Mode status (set externally)


# ============================================================================
# SECRETS LOADING
# ============================================================================

def load_secrets_json():
    """Load secrets from JSON file"""
    try:
        with open(SECRETS_JSON, 'r') as f:
            data = json.load(f)
            info("Secrets loaded from secrets.json")
            return data
    except:
        warning("Could not load secrets.json")
        return {}


def apply_secrets():
    """Apply secrets to global variables"""
    global WIFI_SSID, WIFI_PASSWORD, SMS_USERNAME, SMS_RECIPIENTS, SMS_API_KEY
    
    data = load_secrets_json()
    if not data:
        return
    
    WIFI_SSID = data.get("WIFI_SSID", WIFI_SSID)
    WIFI_PASSWORD = data.get("WIFI_PASSWORD", WIFI_PASSWORD)
    SMS_USERNAME = data.get("SMS_USERNAME", SMS_USERNAME)
    SMS_RECIPIENTS = data.get("SMS_RECIPIENTS", SMS_RECIPIENTS)
    SMS_API_KEY = data.get("SMS_API_KEY", SMS_API_KEY)


def check_internet_available(sms):
    """Check if internet is available"""
    try:
        if not network:
            return False
        
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            return False
        
        return sms.test_internet(config.INTERNET_TEST_TIMEOUT_S)
    except:
        return False


# ============================================================================
# PRESCRIPTION INPUT FUNCTIONS
# ============================================================================

def input_volume(lcd, keypad_input):
    """Input target volume via keypad"""
    lcd.clear()
    lcd_line(lcd, 0, "IV PRESCRIPTION")
    lcd_line(lcd, 1, "Enter Volume (mL):")
    lcd_line(lcd, 3, "#=OK *=Backspace")
    
    keypad_input.clear()
    
    while True:
        status, buffer = keypad_input.process_key()
        
        if status == 'digit' or status == 'backspace':
            lcd_line(lcd, 2, f"Input: {buffer}")
        
        elif status == 'confirm':
            value = keypad_input.get_value()
            if value and config.MIN_VOLUME_ML <= value <= config.MAX_VOLUME_ML:
                info(f"Volume entered: {value} mL")
                return value
            else:
                lcd_line(lcd, 2, f"Invalid! 1-{config.MAX_VOLUME_ML}")
                utime.sleep(1)
                keypad_input.clear()
                lcd_line(lcd, 2, f"Input: ")
        
        utime.sleep_ms(config.BUTTON_CHECK_INTERVAL_MS)
        gc.collect()


def input_duration(lcd, keypad_input):
    """Input duration via keypad"""
    lcd.clear()
    lcd_line(lcd, 0, "IV PRESCRIPTION")
    lcd_line(lcd, 1, "Enter Time (min):")
    lcd_line(lcd, 3, "#=OK *=Backspace")
    
    keypad_input.clear()
    
    while True:
        status, buffer = keypad_input.process_key()
        
        if status == 'digit' or status == 'backspace':
            lcd_line(lcd, 2, f"Input: {buffer}")
        
        elif status == 'confirm':
            value = keypad_input.get_value()
            if value and config.MIN_DURATION_MIN <= value <= config.MAX_DURATION_MIN:
                info(f"Duration entered: {value} min")
                return value
            else:
                lcd_line(lcd, 2, f"Invalid! 1-{config.MAX_DURATION_MIN}")
                utime.sleep(1)
                keypad_input.clear()
                lcd_line(lcd, 2, f"Input: ")
        
        utime.sleep_ms(config.BUTTON_CHECK_INTERVAL_MS)
        gc.collect()


def input_drip_factor(lcd, keypad_input):
    """Input drip factor via keypad (optional)"""
    lcd.clear()
    lcd_line(lcd, 0, "IV PRESCRIPTION")
    lcd_line(lcd, 1, f"Drip Factor gtt/mL")
    lcd_line(lcd, 2, f"*=Use Default ({config.DEFAULT_DRIP_FACTOR})")
    lcd_line(lcd, 3, "#=OK")
    
    keypad_input.clear()
    
    while True:
        status, buffer = keypad_input.process_key()
        
        if status == 'default':
            info(f"Using default drip factor: {config.DEFAULT_DRIP_FACTOR}")
            return config.DEFAULT_DRIP_FACTOR
        
        elif status == 'digit' or status == 'backspace':
            lcd_line(lcd, 2, f"Input: {buffer}")
        
        elif status == 'confirm':
            value = keypad_input.get_value()
            if value and 1 <= value <= 100:  # Reasonable range
                info(f"Drip factor entered: {value}")
                return value
            else:
                lcd_line(lcd, 2, "Invalid! 1-100")
                utime.sleep(1)
                keypad_input.clear()
                lcd_line(lcd, 2, f"*=Default ({config.DEFAULT_DRIP_FACTOR})")
        
        utime.sleep_ms(config.BUTTON_CHECK_INTERVAL_MS)
        gc.collect()


# ============================================================================
# MAIN PROGRAM
# ============================================================================

def main():
    """Main program entry point"""
    info("=== IV Monitoring System Starting ===")
    
    # Load secrets
    apply_secrets()
    
    # ========================================================================
    # HARDWARE INITIALIZATION
    # ========================================================================
    
    info("Initializing hardware...")
    
    # I2C and LCD
    i2c = I2C(0, scl=Pin(config.PIN_I2C_SCL), sda=Pin(config.PIN_I2C_SDA), freq=config.I2C_FREQ)
    lcd = I2cLcd(i2c, config.LCD_I2C_ADDR, config.LCD_ROWS, config.LCD_COLS)
    
    # Buttons
    btn_ack = DebouncedButton(config.PIN_BUTTON_ACK)
    btn_new = DebouncedButton(config.PIN_BUTTON_NEW)
    btn_term = DebouncedButton(config.PIN_BUTTON_TERM)
    btn_cal = DebouncedButton(config.PIN_BUTTON_CAL)
    
    # LEDs
    led_red = Pin(config.PIN_LED_RED, Pin.OUT)
    led_yellow = Pin(config.PIN_LED_YELLOW, Pin.OUT)
    led_green = Pin(config.PIN_LED_GREEN, Pin.OUT)
    
    # Buzzer
    buzzer = Buzzer(config.PIN_BUZZER)
    
    # Keypad
    keypad = Keypad(config.PIN_KEYPAD_ROWS, config.PIN_KEYPAD_COLS)
    keypad_input = KeypadInput(keypad, max_digits=4)
    
    # Sensors
    drop_sensor = DropSensor(config.PIN_DROP_IR, config.DROP_DEBOUNCE_MS)
    bubble_detector = BubbleDetector(
        config.PIN_BUBBLE_IR,
        config.PIN_BUBBLE_SLOT,
        config.BUBBLE_CONFIRM_WINDOW_MS
    )
    
    # SMS
    sms = SmsSender(SMS_USERNAME, SMS_API_KEY, SMS_RECIPIENTS)
    
    # Display splash screen
    lcd.clear()
    lcd_line(lcd, 0, "IV MONITORING SYSTEM")
    lcd_line(lcd, 1, "Drop Counter + Bubble")
    lcd_line(lcd, 2, "Booting...")
    utime.sleep(2)
    
    # ========================================================================
    # NETWORK MODE CHECK
    # ========================================================================
    
    info("Checking network connectivity...")
    lcd.clear()
    lcd_line(lcd, 0, "Checking Network...")
    
    mode = config.MODE_LOCAL_ONLY
    
    # Try WiFi connection
    if WIFI_SSID:
        lcd_line(lcd, 1, "Connecting WiFi...")
        if sms.connect_wifi(WIFI_SSID, WIFI_PASSWORD, config.CONNECT_TIMEOUT_S):
            lcd_line(lcd, 1, "WiFi: OK")
            
            # Test internet
            lcd_line(lcd, 2, "Testing Internet...")
            if check_internet_available(sms):
                mode = config.MODE_ONLINE
                lcd_line(lcd, 2, "Internet: OK")
                info("Mode: ONLINE (WiFi + Internet)")
            else:
                lcd_line(lcd, 2, "Internet: FAIL")
                warning("Mode: LOCAL-ONLY (No Internet)")
        else:
            lcd_line(lcd, 1, "WiFi: FAIL")
            warning("Mode: LOCAL-ONLY (No WiFi)")
    else:
        lcd_line(lcd, 1, "No WiFi configured")
        warning("Mode: LOCAL-ONLY (No credentials)")
    
    lcd_line(lcd, 3, f"Mode: {mode.upper()}")
    utime.sleep(2)
    
    # ========================================================================
    # MAIN STATE MACHINE LOOP
    # ========================================================================
    
    state = config.STATE_PRESCRIPTION_INPUT
    prescription = Prescription()
    monitoring_state = None  # type: MonitoringState | None
    
    alarm_silenced = False
    last_network_check = utime.time()
    last_lcd_update = utime.ticks_ms()
    
    info("Entering main loop...")
    
    while state != config.STATE_TERMINATED:
        
        # ====================================================================
        # STATE: PRESCRIPTION INPUT
        # ====================================================================
        
        if state == config.STATE_PRESCRIPTION_INPUT:
            info("State: PRESCRIPTION INPUT")
            lcd.clear()
            lcd_line(lcd, 0, "PRESCRIPTION ENTRY")
            lcd_line(lcd, 1, "Preparing...")
            utime.sleep(1)
            
            # Reset prescription
            prescription.reset()
            
            # Input volume
            volume = input_volume(lcd, keypad_input)
            prescription.set_volume(volume)
            
            # Input duration
            duration = input_duration(lcd, keypad_input)
            prescription.set_duration(duration)
            
            # Input drip factor
            drip_factor = input_drip_factor(lcd, keypad_input)
            prescription.set_drip_factor(drip_factor)
            
            # Display calculated rate
            lcd.clear()
            lcd_line(lcd, 0, "PRESCRIPTION SET")
            lcd_line(lcd, 1, f"Vol: {prescription.target_volume_ml} mL")
            lcd_line(lcd, 2, f"Time: {prescription.duration_minutes} min")
            lcd_line(lcd, 3, f"Set: {int(prescription.gtt_per_min_target or 0)} gtt/min")
            utime.sleep(3)
            
            # Initialize monitoring state
            monitoring_state = MonitoringState(prescription)
            monitoring_state.start_monitoring()
            
            # Reset sensors
            drop_sensor.reset()
            bubble_detector.reset()
            
            # Send start SMS
            if mode == config.MODE_ONLINE:
                sms.send(f"IV monitoring started: {prescription.target_volume_ml}mL over {prescription.duration_minutes}min (0% delivered).")
            monitoring_state.milestone_flags[0] = True
            
            info(f"Prescription: {prescription.target_volume_ml}mL / {prescription.duration_minutes}min / {prescription.drip_factor_gtt_ml}gtt/mL")
            
            state = config.STATE_MONITORING
        
        # ====================================================================
        # STATE: MONITORING
        # ====================================================================
        
        elif state == config.STATE_MONITORING:
            # Ensure monitoring_state is initialized
            if monitoring_state is None:
                warning("Monitoring state not initialized, returning to prescription")
                state = config.STATE_PRESCRIPTION_INPUT
                continue
            
            # Update sensors
            drop_detected = drop_sensor.update()
            bubble_detected = bubble_detector.update()
            
            # Update monitoring state from drops
            total_drops = drop_sensor.get_total_drops()
            drops_per_min = drop_sensor.get_drops_per_minute()
            monitoring_state.update_from_drops(total_drops, drops_per_min)
            
            # Check for bubble alarm (highest priority)
            if bubble_detected or bubble_detector.is_bubble_detected():
                state = config.STATE_BUBBLE_ALARM
                alarm_silenced = False
                continue
            
            # Check for no-flow condition
            time_since_drop = drop_sensor.get_time_since_last_drop()
            if time_since_drop > (config.DROP_CONFIRM_TIMEOUT_SEC * 1000):
                if monitoring_state.is_volume_complete():
                    state = config.STATE_COMPLETE
                    alarm_silenced = False
                    continue
                else:
                    state = config.STATE_NO_FLOW
                    alarm_silenced = False
                    continue
            
            # Check for time elapsed
            if monitoring_state.is_time_elapsed():
                if monitoring_state.is_volume_complete():
                    state = config.STATE_COMPLETE
                    alarm_silenced = False
                    continue
                else:
                    state = config.STATE_TIME_ELAPSED
                    alarm_silenced = False
                    continue
            
            # Update LCD
            now_ms = utime.ticks_ms()
            if utime.ticks_diff(now_ms, last_lcd_update) >= config.LCD_UPDATE_INTERVAL_MS:
                display_monitoring(lcd, monitoring_state)
                
                # Line 3: Status
                if monitoring_state.remaining_ml < config.LOW_VOLUME_THRESHOLD_ML:
                    if mode == config.MODE_ONLINE:
                        lcd_line(lcd, 3, "LOW VOLUME ALERT")
                    else:
                        lcd_line(lcd, 3, "LOW VOL SMS:OFF")
                else:
                    if mode == config.MODE_ONLINE:
                        lcd_line(lcd, 3, "ONLINE  SMS ON")
                    else:
                        lcd_line(lcd, 3, "LOCAL ONLY SMS OFF")
                
                last_lcd_update = now_ms
            
            # Update LEDs
            update_leds(led_red, led_yellow, led_green, monitoring_state.remaining_ml)
            
            # Check milestone alerts
            for milestone in config.MILESTONES:
                if monitoring_state.check_milestone(milestone):
                    info(f"Milestone: {milestone}%")
                    if mode == config.MODE_ONLINE and milestone > 0:
                        sms.send(f"IV delivered {milestone}%.")
            
            # Low volume alert
            if monitoring_state.remaining_ml < config.LOW_VOLUME_THRESHOLD_ML:
                if not monitoring_state.low_volume_sent:
                    if mode == config.MODE_ONLINE:
                        sms.send(f"IV low volume ({int(monitoring_state.remaining_ml)} mL).")
                    monitoring_state.low_volume_sent = True
                
                # Buzzer for low volume
                if not alarm_silenced:
                    buzzer.set_mode(Buzzer.MODE_LOW)
                else:
                    buzzer.set_mode(Buzzer.MODE_OFF)
            else:
                buzzer.set_mode(Buzzer.MODE_OFF)
            
            # Periodic network check
            if utime.time() - last_network_check >= config.NETWORK_RECHECK_SEC:
                last_network_check = utime.time()
                if check_internet_available(sms):
                    if mode != config.MODE_ONLINE:
                        info("Network restored - switching to ONLINE mode")
                        mode = config.MODE_ONLINE
                else:
                    if mode != config.MODE_LOCAL_ONLY:
                        warning("Network lost - switching to LOCAL-ONLY mode")
                        mode = config.MODE_LOCAL_ONLY
            
            # Button checks
            if btn_ack.pressed():
                info("Acknowledge button pressed")
                alarm_silenced = True
                buzzer.set_mode(Buzzer.MODE_OFF)
            
            if btn_new.pressed():
                info("New IV button pressed")
                state = config.STATE_PRESCRIPTION_INPUT
                buzzer.set_mode(Buzzer.MODE_OFF)
                continue
            
            if btn_cal.pressed():
                info("Calibration button pressed - resetting counters")
                drop_sensor.reset()
                monitoring_state.reset_counters()
                alarm_silenced = False
                lcd.clear()
                lcd_line(lcd, 0, "COUNTERS RESET")
                lcd_line(lcd, 1, "Prescription kept")
                lcd_line(lcd, 2, "Monitoring...")
                utime.sleep(2)
            
            if btn_term.pressed():
                info("Terminate button pressed")
                state = config.STATE_TERMINATED
                continue
        
        # ====================================================================
        # STATE: BUBBLE ALARM
        # ====================================================================
        
        elif state == config.STATE_BUBBLE_ALARM:
            # Ensure monitoring_state is initialized
            if monitoring_state is None:
                state = config.STATE_PRESCRIPTION_INPUT
                continue
            
            info("State: BUBBLE ALARM")
            
            # Display bubble alert
            lcd.clear()
            lcd_line(lcd, 0, "** BUBBLE DETECTED **")
            lcd_line(lcd, 1, "CHECK IV LINE!")
            lcd_line(lcd, 2, "Press ACK to clear")
            lcd_line(lcd, 3, mode.upper())
            
            # All LEDs red
            led_red.on()
            led_yellow.off()
            led_green.off()
            
            # Send SMS (once)
            if mode == config.MODE_ONLINE and not monitoring_state.bubble_sent:
                sms.send("BUBBLE DETECTED - CHECK IV LINE")
                monitoring_state.bubble_sent = True
            
            # Bubble alarm sound
            if not alarm_silenced:
                buzzer.set_mode(Buzzer.MODE_BUBBLE)
            else:
                buzzer.set_mode(Buzzer.MODE_OFF)
            
            # Wait for acknowledge
            if btn_ack.pressed():
                info("Bubble acknowledged")
                alarm_silenced = True
                buzzer.set_mode(Buzzer.MODE_OFF)
                bubble_detector.clear_bubble()
                state = config.STATE_MONITORING
            
            if btn_term.pressed():
                state = config.STATE_TERMINATED
        
        # ====================================================================
        # STATE: NO FLOW / OCCLUSION
        # ====================================================================
        
        elif state == config.STATE_NO_FLOW:
            # Ensure monitoring_state is initialized
            if monitoring_state is None:
                state = config.STATE_PRESCRIPTION_INPUT
                continue
            
            info("State: NO FLOW")
            
            lcd.clear()
            lcd_line(lcd, 0, "** NO FLOW **")
            lcd_line(lcd, 1, "Check line/clamp")
            lcd_line(lcd, 2, f"Vol: {int(monitoring_state.delivered_ml)}/{prescription.target_volume_ml}mL")
            lcd_line(lcd, 3, "ACK=Continue")
            
            # Red LED
            led_red.on()
            led_yellow.off()
            led_green.off()
            
            # Send SMS (once)
            if mode == config.MODE_ONLINE and not monitoring_state.no_flow_sent:
                sms.send(f"NO FLOW - Check IV line ({int(monitoring_state.delivered_ml)}mL delivered)")
                monitoring_state.no_flow_sent = True
            
            # No-flow alarm sound
            if not alarm_silenced:
                buzzer.set_mode(Buzzer.MODE_NO_FLOW)
            else:
                buzzer.set_mode(Buzzer.MODE_OFF)
            
            # Check if flow resumes
            drop_sensor.update()
            if drop_sensor.get_time_since_last_drop() < 5000:  # Flow resumed
                info("Flow resumed")
                alarm_silenced = False
                monitoring_state.no_flow_sent = False
                state = config.STATE_MONITORING
            
            if btn_ack.pressed():
                info("No-flow acknowledged")
                alarm_silenced = True
                buzzer.set_mode(Buzzer.MODE_OFF)
            
            if btn_new.pressed():
                state = config.STATE_PRESCRIPTION_INPUT
            
            if btn_term.pressed():
                state = config.STATE_TERMINATED
        
        # ====================================================================
        # STATE: TIME ELAPSED (UNDERDELIVERED)
        # ====================================================================
        
        elif state == config.STATE_TIME_ELAPSED:
            # Ensure monitoring_state is initialized
            if monitoring_state is None:
                state = config.STATE_PRESCRIPTION_INPUT
                continue
            
            info("State: TIME ELAPSED (underdelivered)")
            
            lcd.clear()
            lcd_line(lcd, 0, "** TIME ELAPSED **")
            lcd_line(lcd, 1, "Volume incomplete")
            lcd_line(lcd, 2, f"{int(monitoring_state.delivered_ml)}/{prescription.target_volume_ml}mL ({int(monitoring_state.percent_delivered)}%)")
            lcd_line(lcd, 3, "ACK=Continue")
            
            # Yellow LED
            led_red.off()
            led_yellow.on()
            led_green.off()
            
            # Send SMS (once)
            if mode == config.MODE_ONLINE and not monitoring_state.time_elapsed_sent:
                sms.send(f"TIME ELAPSED - Volume incomplete: {int(monitoring_state.delivered_ml)}mL/{prescription.target_volume_ml}mL")
                monitoring_state.time_elapsed_sent = True
            
            # Alert sound
            if not alarm_silenced:
                buzzer.set_mode(Buzzer.MODE_LOW)
            else:
                buzzer.set_mode(Buzzer.MODE_OFF)
            
            # Continue monitoring to completion if flow continues
            drop_sensor.update()
            total_drops = drop_sensor.get_total_drops()
            monitoring_state.update_from_drops(total_drops, drop_sensor.get_drops_per_minute())
            
            if monitoring_state.is_volume_complete():
                state = config.STATE_COMPLETE
            
            if btn_ack.pressed():
                info("Time elapsed acknowledged")
                alarm_silenced = True
                buzzer.set_mode(Buzzer.MODE_OFF)
                state = config.STATE_MONITORING
            
            if btn_new.pressed():
                state = config.STATE_PRESCRIPTION_INPUT
            
            if btn_term.pressed():
                state = config.STATE_TERMINATED
        
        # ====================================================================
        # STATE: COMPLETE
        # ====================================================================
        
        elif state == config.STATE_COMPLETE:
            # Ensure monitoring_state is initialized
            if monitoring_state is None:
                state = config.STATE_PRESCRIPTION_INPUT
                continue
            
            info("State: COMPLETE")
            
            lcd.clear()
            lcd_line(lcd, 0, "INFUSION COMPLETE")
            lcd_line(lcd, 1, f"{int(monitoring_state.delivered_ml)}mL delivered")
            lcd_line(lcd, 2, "100%")
            lcd_line(lcd, 3, "Press NEW or TERM")
            
            # Green LED
            led_red.off()
            led_yellow.off()
            led_green.on()
            
            # Send SMS (once)
            if not monitoring_state.milestone_flags[100]:
                if mode == config.MODE_ONLINE:
                    sms.send("IV completed 100%.")
                monitoring_state.milestone_flags[100] = True
            
            # Completion tone
            if not alarm_silenced:
                buzzer.set_mode(Buzzer.MODE_COMPLETE)
            else:
                buzzer.set_mode(Buzzer.MODE_OFF)
            
            if btn_ack.pressed():
                alarm_silenced = True
                buzzer.set_mode(Buzzer.MODE_OFF)
            
            if btn_new.pressed():
                state = config.STATE_PRESCRIPTION_INPUT
                buzzer.set_mode(Buzzer.MODE_OFF)
            
            if btn_term.pressed():
                state = config.STATE_TERMINATED
        
        # Update buzzer
        buzzer.update()
        
        # Main loop delay
        utime.sleep_ms(config.MAIN_LOOP_DELAY_MS)
        gc.collect()
    
    # ========================================================================
    # SHUTDOWN
    # ========================================================================
    
    info("Terminating session...")
    buzzer.set_mode(Buzzer.MODE_OFF)
    led_red.off()
    led_yellow.off()
    led_green.off()
    
    lcd.clear()
    lcd_line(lcd, 0, "SESSION ENDED")
    lcd_line(lcd, 1, "System terminated")
    lcd_line(lcd, 2, "")
    lcd_line(lcd, 3, "")
    
    info("=== IV Monitoring System Stopped ===")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        critical(f"Fatal error: {e}")
        raise
