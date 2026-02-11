"""
Configuration Constants for IV Monitoring System
All system-wide configuration values and defaults
"""

# ============================================================================
# PRESCRIPTION DEFAULTS
# ============================================================================

DEFAULT_DRIP_FACTOR = 20  # gtt/mL - default drip factor if not specified
MIN_VOLUME_ML = 1         # Minimum prescription volume
MAX_VOLUME_ML = 1500      # Maximum prescription volume
MIN_DURATION_MIN = 1      # Minimum infusion duration (minutes)
MAX_DURATION_MIN = 1440   # Maximum infusion duration (24 hours)

# Valid drip factors (common IV set values)
VALID_DRIP_FACTORS = [10, 15, 20, 60]

# ============================================================================
# SENSOR TIMING AND DETECTION PARAMETERS
# ============================================================================

DROP_DEBOUNCE_MS = 80            # Ignore pulses faster than this (milliseconds)
DROP_CONFIRM_TIMEOUT_SEC = 30    # No-drop timeout for completion/no-flow detection
BUBBLE_CONFIRM_WINDOW_MS = 400   # Both bubble sensors must trigger within this window
NETWORK_RECHECK_SEC = 60         # Internet connectivity recheck interval

# ============================================================================
# ALARM THRESHOLDS
# ============================================================================

LOW_VOLUME_THRESHOLD_ML = 200     # Threshold for low volume alert
WARNING_VOLUME_THRESHOLD_ML = 300 # Threshold for warning LED (yellow)

# Milestone percentages (relative to prescription volume)
MILESTONES = [0, 25, 50, 100]

# ============================================================================
# GPIO PIN ASSIGNMENTS
# ============================================================================

# Buttons
PIN_BUTTON_ACK = 8          # Acknowledge/silence alarm button
PIN_BUTTON_NEW = 9          # New IV / reset prescription button
PIN_BUTTON_TERM = 10        # Terminate session button
PIN_BUTTON_CAL = 12         # Calibration / reset counters button

# LEDs
PIN_LED_RED = 18            # Red LED (critical/fault)
PIN_LED_YELLOW = 19         # Yellow LED (warning)
PIN_LED_GREEN = 20          # Green LED (normal)

# Buzzer
PIN_BUZZER = 11             # Passive buzzer (PWM)

# I2C LCD
PIN_I2C_SDA = 16            # I2C SDA (LCD)
PIN_I2C_SCL = 17            # I2C SCL (LCD)
I2C_FREQ = 400000           # I2C frequency (Hz)
LCD_I2C_ADDR = 0x27         # LCD I2C address

# Sensors
PIN_DROP_IR = 21            # Drop IR sensor output
PIN_BUBBLE_IR = 22          # Bubble IR sensor output
PIN_BUBBLE_SLOT = 26        # Bubble Slot module DO output

# Keypad (4x3 matrix)
PIN_KEYPAD_ROWS = [2, 3, 4, 5]      # Row pins (outputs)
PIN_KEYPAD_COLS = [6, 7, 13]        # Column pins (inputs)

# ============================================================================
# NETWORK AND SMS SETTINGS
# ============================================================================

MODE_ONLINE = "online"           # WiFi + Internet available
MODE_LOCAL_ONLY = "local_only"   # No WiFi or no Internet

CONNECT_TIMEOUT_S = 15           # WiFi connection timeout (seconds)
INTERNET_TEST_TIMEOUT_S = 5      # HTTP GET timeout for internet test
INTERNET_TEST_INTERVAL_S = 60    # Mode recheck interval during monitoring

# Africa's Talking API endpoint for connectivity test
SMS_API_ENDPOINT = "https://api.africastalking.com/version1/messaging"

# ============================================================================
# BUZZER PATTERNS (PWM frequency and timing)
# ============================================================================

BUZZER_FREQ_HZ = 2000           # Buzzer tone frequency
BUZZER_OFF_DUTY = 0             # Buzzer off (0% duty cycle)
BUZZER_ON_DUTY = 512            # Buzzer on (50% duty cycle for 10-bit PWM)

# Buzzer timing patterns (milliseconds)
BUZZER_INTERVAL_LOW = 150       # Low volume alert interval
BUZZER_INTERVAL_COMPLETE = 600  # Completion tone duration
BUZZER_INTERVAL_FAULT = 600     # Fault tone duration
BUZZER_INTERVAL_BUBBLE = 100    # Bubble alarm (rapid beeping)
BUZZER_INTERVAL_NO_FLOW = 200   # No-flow alarm

# ============================================================================
# STATE MACHINE STATES
# ============================================================================

STATE_INIT = "init"
STATE_MODE_CHECK = "mode_check"
STATE_PRESCRIPTION_INPUT = "prescription_input"
STATE_RATE_DISPLAY = "rate_display"
STATE_MONITORING = "monitoring"
STATE_BUBBLE_ALARM = "bubble_alarm"
STATE_NO_FLOW = "no_flow"
STATE_TIME_ELAPSED = "time_elapsed"
STATE_COMPLETE = "complete"
STATE_TERMINATED = "terminated"

# ============================================================================
# LCD DISPLAY SETTINGS
# ============================================================================

LCD_ROWS = 4
LCD_COLS = 20

# Display update interval (milliseconds)
LCD_UPDATE_INTERVAL_MS = 500

# ============================================================================
# MAIN LOOP TIMING
# ============================================================================

MAIN_LOOP_DELAY_MS = 100        # Main loop cycle time (milliseconds)
BUTTON_CHECK_INTERVAL_MS = 50   # Button polling interval

# ============================================================================
# LOGGING SETTINGS
# ============================================================================

LOG_FILE = "system.txt"
LOG_FILE_BACKUP = "system.txt.bak"
LOG_MAX_SIZE = 50000  # Maximum log file size before rotation (bytes)
