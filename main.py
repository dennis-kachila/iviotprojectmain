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

from hx711 import HX711
from i2c_lcd import I2cLcd


FULL_BAG_ML = 1500
LOW_CRITICAL_ML = 200
LOW_WARNING_MIN = 200
LOW_WARNING_MAX = 299

CAL_WEIGHT_G = 500
CAL_FILE = "calibration.json"
SECRETS_JSON = "secrets.json"

MODE_ONLINE = "online"
MODE_LOCAL_ONLY = "local_only"
CONNECT_TIMEOUT_S = 15
INTERNET_TEST_TIMEOUT_S = 5
INTERNET_TEST_INTERVAL_S = 60

# Default configuration (will be overridden by secrets.json if present)
WIFI_SSID = ""
WIFI_PASSWORD = ""

SMS_USERNAME = ""
SMS_RECIPIENTS = []
SMS_API_KEY = ""


PIN_BUTTON_ACK = 8
PIN_BUTTON_NEW = 9
PIN_BUTTON_TERM = 10
PIN_BUTTON_CAL = 12
PIN_BUZZER = 11
PIN_LED_RED = 18
PIN_LED_YELLOW = 19
PIN_LED_GREEN = 20
PIN_HX_DT = 26
PIN_HX_SCK = 27
PIN_I2C_SDA = 16
PIN_I2C_SCL = 17


class DebouncedButton:
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
                if state == 1:
                    return True
        return False


class Buzzer:
    MODE_OFF = "off"
    MODE_LOW = "low"
    MODE_COMPLETE = "complete"
    MODE_FAULT = "fault"

    def __init__(self, pin):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(2000)
        self.mode = self.MODE_OFF
        self._last_toggle = utime.ticks_ms()
        self._state = 0

    def set_mode(self, mode):
        if mode != self.mode:
            self.mode = mode
            self._state = 0
            self._apply_state(0)
            self._last_toggle = utime.ticks_ms()

    def _apply_state(self, on):
        self.pwm.duty_u16(30000 if on else 0)

    def update(self):
        now = utime.ticks_ms()
        if self.mode == self.MODE_OFF:
            self._apply_state(0)
            return
        if self.mode == self.MODE_FAULT:
            self._apply_state(1)
            return

        interval = 150 if self.mode == self.MODE_LOW else 600
        if utime.ticks_diff(now, self._last_toggle) >= interval:
            self._state = 0 if self._state else 1
            self._apply_state(self._state)
            self._last_toggle = now


class SmsSender:
    def __init__(self, ssid, password, username, recipients, api_key):
        self.ssid = ssid
        self.password = password
        self.username = username
        self.recipients = recipients
        self.api_key = api_key
        self.connected = False
        self.sms = AfricaTalkingSMS(self.username, self.api_key)

    def connect_wifi(self, timeout_s=15):
        if not network or not self.ssid:
            self.connected = False
            return False
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            wlan.connect(self.ssid, self.password)
            start = utime.ticks_ms()
            while not wlan.isconnected():
                if utime.ticks_diff(utime.ticks_ms(), start) > timeout_s * 1000:
                    self.connected = False
                    return False
                utime.sleep_ms(250)
        self.connected = True
        return True

    def test_internet(self, timeout_s=5):
        if not urequests or not self.connected:
            return False
        try:
            response = urequests.get(
                self.sms.endpoint,
                headers={"apiKey": self.api_key},
                timeout=timeout_s,
            )
            response.close()
            return True
        except Exception:
            return False

    def send(self, message):
        if not urequests or not self.connected or not self.api_key:
            return False
        try:
            return self.sms.send(message, self.recipients)
        except Exception:
            return False


class AfricaTalkingSMS:
    def __init__(self, username, api_key):
        self.username = username
        self.api_key = api_key
        self.endpoint = "https://api.africastalking.com/version1/messaging"

    def send(self, message, recipients):
        if not urequests:
            return False
        payload = {
            "username": self.username,
            "to": ",".join(recipients),
            "message": message,
        }
        headers = {"apiKey": self.api_key, "Content-Type": "application/json"}
        response = urequests.post(
            self.endpoint,
            headers=headers,
            data=json.dumps(payload),
        )
        response.close()
        return True


def lcd_line(lcd, line, text):
    lcd.putstr_at(text, line)


def load_calibration():
    try:
        with open(CAL_FILE, "r") as handle:
            data = json.loads(handle.read())
            return data.get("offset"), data.get("scale")
    except OSError:
        return None, None
    except ValueError:
        return None, None


def save_calibration(offset, scale):
    data = {"offset": offset, "scale": scale}
    with open(CAL_FILE, "w") as handle:
        handle.write(json.dumps(data))



def wait_for_press(button, timeout_s=120):
    start = utime.ticks_ms()
    while True:
        if button.pressed():
            return True
        if timeout_s and utime.ticks_diff(utime.ticks_ms(), start) > timeout_s * 1000:
            return False
        utime.sleep_ms(50)


def calibrate_with_button(hx, lcd, button):
    # Step 1: Tare (zero the scale)
    lcd.clear()
    lcd_line(lcd, 0, "STEP 1/2: TARE")
    lcd_line(lcd, 1, "Remove all weight")
    lcd_line(lcd, 2, "Press CAL to tare")
    lcd_line(lcd, 3, "")
    if not wait_for_press(button, 180):
        lcd.clear()
        lcd_line(lcd, 0, "Cal timeout")
        lcd_line(lcd, 1, "Step 1 failed")
        utime.sleep(2)
        return None, None

    lcd.clear()
    lcd_line(lcd, 0, "STEP 1/2: TARE")
    lcd_line(lcd, 1, "Reading...")
    lcd_line(lcd, 2, "Please wait")
    lcd_line(lcd, 3, "")
    
    offset = hx.read_average(20)
    if offset is None:
        lcd.clear()
        lcd_line(lcd, 0, "Sensor error")
        lcd_line(lcd, 1, "Step 1 failed")
        utime.sleep(2)
        return None, None

    # Step 2: Set scale with known weight
    lcd.clear()
    lcd_line(lcd, 0, "STEP 2/2: SCALE")
    lcd_line(lcd, 1, "Place %dg weight" % CAL_WEIGHT_G)
    lcd_line(lcd, 2, "Press CAL to set")
    lcd_line(lcd, 3, "")
    if not wait_for_press(button, 240):
        lcd.clear()
        lcd_line(lcd, 0, "Cal timeout")
        lcd_line(lcd, 1, "Step 2 failed")
        utime.sleep(2)
        return None, None

    lcd.clear()
    lcd_line(lcd, 0, "STEP 2/2: SCALE")
    lcd_line(lcd, 1, "Reading...")
    lcd_line(lcd, 2, "Please wait")
    lcd_line(lcd, 3, "")
    
    reading = hx.read_average(20)
    if reading is None:
        lcd.clear()
        lcd_line(lcd, 0, "Sensor error")
        lcd_line(lcd, 1, "Step 2 failed")
        utime.sleep(2)
        return None, None
    
    scale = (reading - offset) / float(CAL_WEIGHT_G)
    if scale == 0:
        lcd.clear()
        lcd_line(lcd, 0, "Invalid scale")
        lcd_line(lcd, 1, "No weight change")
        utime.sleep(2)
        return None, None
    
    save_calibration(offset, scale)

    lcd.clear()
    lcd_line(lcd, 0, "Cal Complete!")
    lcd_line(lcd, 1, "Data saved")
    lcd_line(lcd, 2, "Offset: %d" % int(offset))
    lcd_line(lcd, 3, "Scale: %.2f" % scale)
    utime.sleep(3)
    return offset, scale


def update_leds(led_red, led_yellow, led_green, remaining):
    led_red.value(0)
    led_yellow.value(0)
    led_green.value(0)
    if remaining <= LOW_CRITICAL_ML:
        led_red.value(1)
    elif LOW_WARNING_MIN <= remaining <= LOW_WARNING_MAX:
        led_yellow.value(1)
    else:
        led_green.value(1)


def compute_percent(delivered):
    if delivered <= 0:
        return 0
    if delivered >= FULL_BAG_ML:
        return 100
    return int((delivered / FULL_BAG_ML) * 100 + 0.5)


def check_internet_available(sms):
    """
    Test if internet/API is reachable.
    Returns True only if wifi AND internet are both OK.
    """
    if not network:
        return False
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        return False
    return sms.test_internet(timeout_s=INTERNET_TEST_TIMEOUT_S)


def apply_secrets():
    global WIFI_SSID, WIFI_PASSWORD, SMS_USERNAME, SMS_RECIPIENTS, SMS_API_KEY
    data = load_secrets_json()
    if not data:
        return
    WIFI_SSID = data.get("WIFI_SSID", WIFI_SSID)
    WIFI_PASSWORD = data.get("WIFI_PASSWORD", WIFI_PASSWORD)
    SMS_USERNAME = data.get("SMS_USERNAME", SMS_USERNAME)
    SMS_RECIPIENTS = data.get("SMS_RECIPIENTS", SMS_RECIPIENTS)
    SMS_API_KEY = data.get("SMS_API_KEY", SMS_API_KEY)


def load_secrets_json():
    try:
        with open(SECRETS_JSON, "r") as handle:
            data = json.loads(handle.read())
    except OSError:
        return {}
    except ValueError:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def main():
    apply_secrets()
    i2c = I2C(0, sda=Pin(PIN_I2C_SDA), scl=Pin(PIN_I2C_SCL), freq=400000)
    lcd = I2cLcd(i2c, 0x27, 4, 20)

    led_red = Pin(PIN_LED_RED, Pin.OUT)
    led_yellow = Pin(PIN_LED_YELLOW, Pin.OUT)
    led_green = Pin(PIN_LED_GREEN, Pin.OUT)

    btn_ack = DebouncedButton(PIN_BUTTON_ACK)
    btn_new = DebouncedButton(PIN_BUTTON_NEW)
    btn_term = DebouncedButton(PIN_BUTTON_TERM)
    btn_cal = DebouncedButton(PIN_BUTTON_CAL)

    buzzer = Buzzer(PIN_BUZZER)

    hx = HX711(PIN_HX_DT, PIN_HX_SCK)

    lcd.show_splash(["IV Monitor", "Booting..."])

    sms = SmsSender(WIFI_SSID, WIFI_PASSWORD, SMS_USERNAME, SMS_RECIPIENTS, SMS_API_KEY)
    wifi_ok = sms.connect_wifi()

    mode = MODE_ONLINE if wifi_ok and check_internet_available(sms) else MODE_LOCAL_ONLY
    last_internet_check = utime.ticks_ms()

    lcd.clear()
    mode_str = "ONLINE" if mode == MODE_ONLINE else "LOCAL ONLY"
    lcd_line(lcd, 0, "WiFi: %s" % ("OK" if wifi_ok else "OFF"))
    lcd_line(lcd, 1, "Mode: %s" % mode_str)
    lcd_line(lcd, 2, "Checking calib...")
    utime.sleep(1)

    offset, scale = load_calibration()
    if offset is None or scale is None:
        lcd.clear()
        lcd_line(lcd, 0, "No calibration")
        lcd_line(lcd, 1, "found. Starting")
        lcd_line(lcd, 2, "calibration...")
        utime.sleep(2)
        offset, scale = calibrate_with_button(hx, lcd, btn_cal)
    else:
        lcd.clear()
        lcd_line(lcd, 0, "Calibration OK")
        lcd_line(lcd, 1, "Loaded from file")
        lcd_line(lcd, 2, "Offset: %d" % int(offset))
        lcd_line(lcd, 3, "Scale: %.2f" % scale)
        utime.sleep(2)

    if not isinstance(offset, (int, float)) or not isinstance(scale, (int, float)) or offset is None or scale is None:
        lcd.clear()
        lcd_line(lcd, 0, "Sensor fault")
        lcd_line(lcd, 1, "Check load")
        buzzer.set_mode(Buzzer.MODE_FAULT)
        while True:
            buzzer.update()
            if btn_term.pressed():
                buzzer.set_mode(Buzzer.MODE_OFF)
                lcd.clear()
                lcd_line(lcd, 0, "SESSION ENDED")
                return
            utime.sleep_ms(100)

    sms_flags = {"start": False, "25": False, "50": False, "100": False, "low": False}
    alarm_silenced = False
    last_alarm = None

    lcd.clear()
    lcd_line(lcd, 0, "Monitoring...")
    mode_str = "ONLINE" if mode == MODE_ONLINE else "LOCAL"

    if mode == MODE_ONLINE and not sms_flags["start"]:
        sms.send("IV monitoring started (0% delivered).")
        sms_flags["start"] = True

    while True:
        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_internet_check) > INTERNET_TEST_INTERVAL_S * 1000:
            prev_mode = mode
            mode = MODE_ONLINE if wifi_ok and check_internet_available(sms) else MODE_LOCAL_ONLY
            if mode != prev_mode:
                mode_str = "ONLINE" if mode == MODE_ONLINE else "LOCAL"
            last_internet_check = now

        if btn_term.pressed():
            buzzer.set_mode(Buzzer.MODE_OFF)
            led_red.value(0)
            led_yellow.value(0)
            led_green.value(0)
            lcd.clear()
            lcd_line(lcd, 0, "SESSION ENDED")
            return

        if btn_cal.pressed():
            buzzer.set_mode(Buzzer.MODE_OFF)
            new_offset, new_scale = calibrate_with_button(hx, lcd, btn_cal)
            if new_offset is not None and new_scale is not None:
                offset, scale = new_offset, new_scale
                lcd.clear()
                lcd_line(lcd, 0, "Monitoring...")
            else:
                lcd.clear()
                lcd_line(lcd, 0, "Cal failed")
                lcd_line(lcd, 1, "Keep previous")
                utime.sleep(2)
                lcd.clear()
                lcd_line(lcd, 0, "Monitoring...")

        if btn_ack.pressed():
            alarm_silenced = True

        if btn_new.pressed():
            alarm_silenced = False
            sms_flags = {"start": False, "25": False, "50": False, "100": False, "low": False}
            lcd.clear()
            lcd_line(lcd, 0, "New IV")
            lcd_line(lcd, 1, "Taring...")
            utime.sleep(2)
            offset = hx.read_average(15)
            lcd.clear()
            lcd_line(lcd, 0, "Monitoring...")
            if mode == MODE_ONLINE and not sms_flags["start"]:
                sms.send("IV monitoring started (0% delivered).")
                sms_flags["start"] = True

        raw = hx.read_average(5)
        if raw is None:
            buzzer.set_mode(Buzzer.MODE_FAULT)
            lcd.clear()
            lcd_line(lcd, 0, "Sensor fault")
            lcd_line(lcd, 1, "No data")
            last_alarm = Buzzer.MODE_FAULT
            buzzer.update()
            utime.sleep_ms(200)
            continue

        if offset is None or scale is None or scale == 0:
            buzzer.set_mode(Buzzer.MODE_FAULT)
            lcd.clear()
            lcd_line(lcd, 0, "Sensor fault")
            lcd_line(lcd, 1, "Bad calib")
            last_alarm = Buzzer.MODE_FAULT
            buzzer.update()
            utime.sleep_ms(200)
            continue

        grams = (raw - offset) / scale
        if grams < -50 or grams > FULL_BAG_ML + 500:
            buzzer.set_mode(Buzzer.MODE_FAULT)
            lcd.clear()
            lcd_line(lcd, 0, "Sensor fault")
            lcd_line(lcd, 1, "Out of range")
            last_alarm = Buzzer.MODE_FAULT
            buzzer.update()
            utime.sleep_ms(200)
            continue

        remaining = int(max(0, min(FULL_BAG_ML, grams)))
        delivered = FULL_BAG_ML - remaining
        percent = compute_percent(delivered)

        lcd_line(lcd, 0, "Remain: %4d mL" % remaining)
        lcd_line(lcd, 1, "Done:   %3d %%" % percent)
        lcd_line(lcd, 2, "Delivered:%4d" % delivered)
        mode_indicator = "OK" if mode == MODE_ONLINE else "LOCAL"
        lcd_line(lcd, 3, "Status: %s" % mode_indicator)

        update_leds(led_red, led_yellow, led_green, remaining)

        alarm_mode = Buzzer.MODE_OFF
        if remaining <= LOW_CRITICAL_ML:
            alarm_mode = Buzzer.MODE_LOW
        if percent >= 100:
            alarm_mode = Buzzer.MODE_COMPLETE

        if alarm_mode != last_alarm:
            alarm_silenced = False
            last_alarm = alarm_mode

        if alarm_mode != Buzzer.MODE_OFF and not alarm_silenced:
            buzzer.set_mode(alarm_mode)
        else:
            buzzer.set_mode(Buzzer.MODE_OFF)

        if remaining <= LOW_CRITICAL_ML:
            lcd_line(lcd, 3, "Status: LOW")
            if mode == MODE_ONLINE and not sms_flags["low"]:
                sms.send("IV low volume (%d mL)." % remaining)
                sms_flags["low"] = True
            elif mode == MODE_LOCAL_ONLY and not sms_flags["low"]:
                lcd_line(lcd, 3, "LOW SMS:OFF")
                sms_flags["low"] = True

        if percent >= 25 and not sms_flags["25"]:
            if mode == MODE_ONLINE:
                sms.send("IV delivered 25%.")
            sms_flags["25"] = True
        if percent >= 50 and not sms_flags["50"]:
            if mode == MODE_ONLINE:
                sms.send("IV delivered 50%.")
            sms_flags["50"] = True
        if percent >= 100 and not sms_flags["100"]:
            lcd_line(lcd, 3, "Status: DONE")
            if mode == MODE_ONLINE:
                sms.send("IV completed 100%.")
            sms_flags["100"] = True

        buzzer.update()
        gc.collect()
        utime.sleep_ms(500)


if __name__ == "__main__":
    main()
