# AI Agent Guidelines for IV Fluid Monitoring System

## Project Overview

This is an **IoT-based intravenous (IV) fluid monitoring system** designed to assist nurses and clinicians by continuously monitoring the volume of IV fluid delivered to a patient and providing **visual, audible, and SMS alerts** at critical stages of infusion.

The system uses a **load cell sensor** interfaced through an **HX711 24-bit ADC** to measure the weight of an IV fluid bag. The measured weight is converted into remaining fluid volume (in milliliters) and percentage delivered. A **Raspberry Pi Pico / Pico W** acts as the main controller, managing sensing, computation, display, alerts, and wireless communication.

The system operates in two modes: **ONLINE** (with SMS notifications via Africa's Talking) and **LOCAL-ONLY** (local alerts only, graceful degradation without internet).

The system supports **human-in-the-loop control** through push buttons, ensuring safe operation aligned with clinical workflows. The monitoring process has clearly defined **START**, **CONTINUOUS MONITORING**, and **END/TERMINATION** states.

## Hardware Requirements and Bill of Materials

### Main Microcontroller
- **Raspberry Pi Pico W** or **Pico WH** (with wireless capability for SMS)

### Sensors and Measurement
- **Load Cell:** 5kg scale analog load cell
- **HX711 24-bit ADC Amplifier Module:** for load cell signal conditioning

### User Interface
- **20x4 I2C LCD Display** (I2C address 0x27)
- **4x Push Buttons:** 
  - Acknowledge (GPIO8)
  - New IV (GPIO9)
  - Terminate (GPIO10)
  - Calibration (GPIO12)

### Alerts and Indicators
- **3x LEDs:**
  - Red LED (GPIO18) — Critical low volume (<200 mL) or fault
  - Yellow LED (GPIO19) — Warning level (200-299 mL)
  - Green LED (GPIO20) — Normal operation (300-1500 mL)
- **Passive Buzzer:** PWM-driven (GPIO11)

### Passive Components
- **Resistors:**
  - 1kΩ resistors (×7) — LED current limiting
  - 10kΩ resistors (×4) — Button pull-down
- **Breadboard and jumper wires**
- **USB power supply** (5V, 2A minimum for Pico W)

## GPIO Pin Mapping (Critical - All Hardcoded in main.py lines 37-46)

| Component | GPIO Pin | Mode | Description |
|-----------|----------|------|-------------|
| ACK Button | GPIO8 | Input (pull-down) | Acknowledge/silence alarms |
| NEW Button | GPIO9 | Input (pull-down) | Start monitoring new IV bag |
| TERM Button | GPIO10 | Input (pull-down) | Terminate session |
| CAL Button | GPIO12 | Input (pull-down) | Start calibration process |
| Buzzer | GPIO11 | Output (PWM) | Audible alerts (2kHz frequency) |
| I2C SDA | GPIO16 | I2C0 SDA | LCD data line |
| I2C SCL | GPIO17 | I2C0 SCL | LCD clock line |
| Red LED | GPIO18 | Output | Critical low volume or fault indicator |
| Yellow LED | GPIO19 | Output | Warning level indicator |
| Green LED | GPIO20 | Output | Normal operation indicator |
| HX711 DT | GPIO26 | Input | Load cell data output (DOUT) |
| HX711 SCK | GPIO27 | Output | Load cell serial clock (SCK) |

**IMPORTANT:** Pin mapping is hardcoded. Changes require updating constants AND physical hardware wiring.

## Architecture & Data Flow

### Core Components & Files

- **main.py** (614 lines): Main application state machine, handles boot sequence, calibration, monitoring loop, and alert logic; fully instrumented with logging
- **hx711.py**: Load cell driver for reading raw weight data from 24-bit ADC with SPI protocol; includes device diagnostics logging
- **i2c_lcd.py** / **lcd_api.py**: LCD display drivers (20x4 I2C display at address 0x27)
- **logger.py**: Custom MicroPython-compatible logging module; writes timestamped logs to `system.log` with rotation
- **secrets.json**: WiFi SSID/password and Africa's Talking SMS API credentials (user-provided, not in repo)
- **calibration.json**: Persisted calibration offset/scale (generated after first calibration)

### Main State Machine Flow

1. **BOOT PHASE:**
   - Load secrets from `secrets.json`
   - Initialize GPIO pins (buttons, LEDs, buzzer, HX711, I2C)
   - Display splash screen on LCD
   - Connect to WiFi (with 15s timeout)
   - Test internet connectivity (5s timeout to Africa's Talking API)
   - Determine mode: ONLINE (WiFi + Internet OK) or LOCAL-ONLY (no WiFi or no internet)
   - Display mode status on LCD

2. **CALIBRATION PHASE:**
   - Check if `calibration.json` exists
   - If missing:
     - Display "Calibration - Remove weight" on LCD
     - Wait for CAL button press (180s timeout) → read offset
     - Display "Place 500g - Press CAL to set" on LCD
     - Wait for CAL button press (240s timeout) → read scale factor
     - Validate scale ≠ 0
     - Save to `calibration.json`
     - Display "Calibration OK - Saved"
   - If invalid: trigger sensor fault and wait for TERM button

3. **MONITORING LOOP** (main while loop, 500ms cycle):
   - Every 500ms: Read HX711 (average 5 readings) → Calculate grams → remaining mL & percentage → Update LCD/LEDs/Buzzer
   - Every 60s: Retest internet connectivity (can trigger MODE_ONLINE ↔ MODE_LOCAL_ONLY switch)
   - Button events: ACK (silence alarm), NEW (start new IV bag), TERM (end session), CAL (recalibrate)
   - Check alert thresholds (LOW_CRITICAL_ML=200, percentage milestones)
   - Send SMS if ONLINE mode (protected by duplicate flags)
   - Call `gc.collect()` to prevent heap overflow

4. **SHUTDOWN:**
   - Turn off all LEDs and buzzer
   - Display "SESSION ENDED" on LCD
   - Exit main loop

### Key Data Transformations

```python
# Sensor reading to weight
raw_hx711_value = hx.read_average(5)  # 24-bit ADC reading

# Weight to volume (grams)
grams = (raw - offset) / scale

# Clamp to valid range
remaining_mL = max(0, min(FULL_BAG_ML, grams))

# Calculate delivered volume
delivered_mL = FULL_BAG_ML - remaining_mL

# Convert to percentage
percent = (delivered_mL / FULL_BAG_ML) * 100  # 0-100%
```

### Mode Detection & Internet Testing

- **Initial mode detection** (main.py:378-391): WiFi connect → internet test → set MODE
- **Periodic retest** (main.py:401-405): Every 60 seconds via `check_internet_available()`
- **Triggers**: WiFi fails → LOCAL-ONLY; WiFi/internet restored → switches to ONLINE within 60s
- **Internet test method**: Makes HTTP GET to `https://api.africastalking.com/version1/messaging` with 5s timeout
- **Graceful degradation**: SMS failures silently skip; system continues with local alerts

## Critical Workflows & Constants

### Configuration Constants (main.py lines 16-32)

| Constant | Value | Purpose |
|----------|-------|---------|
| `FULL_BAG_ML` | 1500 | Full IV bag volume; defines 100% completion baseline |
| `LOW_CRITICAL_ML` | 200 | Threshold for red LED + low-frequency buzzer (150ms) |
| `LOW_WARNING_MIN` | 200 | Lower bound for yellow LED (200-299 mL) |
| `LOW_WARNING_MAX` | 299 | Upper bound for yellow LED |
| `CAL_WEIGHT_G` | 500 | Reference weight for calibration (grams) |
| `MODE_ONLINE` | "online" | WiFi + Internet both OK |
| `MODE_LOCAL_ONLY` | "local_only" | No WiFi or no internet |
| `CONNECT_TIMEOUT_S` | 15 | WiFi connection timeout (seconds) |
| `INTERNET_TEST_TIMEOUT_S` | 5 | HTTP GET timeout for internet test |
| `INTERNET_TEST_INTERVAL_S` | 60 | Mode recheck interval during monitoring |

**CRITICAL:** `FULL_BAG_ML = 1500` must NOT be modified without proportionally updating all alert thresholds.

### Volume Thresholds & Alert Logic

#### LED Logic (update_leds function)
- `remaining <= LOW_CRITICAL_ML (200 mL)`: **Red LED ON** → critical low volume
- `200 ≤ remaining ≤ 299 mL`: **Yellow LED ON** → warning level
- `remaining > 299 mL`: **Green LED ON** → normal operation

#### Buzzer Modes (Buzzer class)
- `MODE_OFF`: Buzzer silent
- `MODE_LOW`: Blink every 150ms → low volume alert
- `MODE_COMPLETE`: Continuous tone → 100% delivered
- `MODE_FAULT`: Continuous tone → sensor error (no recovery without user action)

**Buzzer Timing:**
- Low volume: 150ms interval (fast beeping)
- Complete/Fault: 600ms = continuous tone

### SMS Alert Thresholds & Flags (ONLINE MODE ONLY)

SMS notifications are sent at:
- **0%**: "IV monitoring started (0% delivered.)" - sent on START or NEW button
- **25%**: "IV delivered 25%." 
- **50%**: "IV delivered 50%."
- **100%**: "IV completed 100%."
- **Low volume**: "IV low volume (X mL)." - when remaining ≤ 200 mL

Duplicate prevention: `sms_flags = {"start": False, "25": False, "50": False, "100": False, "low": False}`

**Important:** SMS flags reset ONLY when pressing NEW button → allows re-sending alerts for new IV bag.

### LCD Display Convention (4 lines, 20 chars max each)

```
Line 0: "Remain: XXXX mL"      # Remaining volume (primary metric)
Line 1: "Done:   XXX %"        # Percentage delivered (0-100%)
Line 2: "Delivered:XXXX"       # Total delivered volume
Line 3: "Status: OK/LOCAL/LOW"  # Mode or alert status
```

Use `lcd_line(lcd, line_num, text)` helper function at main.py:177 for padding/display.

When low volume alert: Line 3 becomes "Status: LOW" or "LOW SMS:OFF" (LOCAL-ONLY mode).
When complete: Line 3 becomes "Status: DONE".
When sensor fault: Display "Sensor fault" + error description.

### Calibration Process (calibrate_with_button function)

**Automatic Check Before Calibration:**
- System checks if `calibration.json` exists (via `load_calibration()`)
- If file exists with valid offset/scale → **Skip calibration**, display "Calibration OK - Loaded from file"
- If file missing/invalid → **Start calibration** with explicit step labels on LCD

**Step 1/2 - Tare (180s timeout):**
1. LCD displays: "STEP 1/2: TARE\nRemove all weight\nPress CAL to tare"
2. Wait for CAL button press
3. LCD shows: "STEP 1/2: TARE\nReading...\nPlease wait"
4. Read 20 HX711 samples → compute `offset`
5. If any reading is `None` → return (None, None) → sensor fault with error message

**Step 2/2 - Scale (240s timeout):**
1. LCD displays: "STEP 2/2: SCALE\nPlace 500g weight\nPress CAL to set"
2. Wait for CAL button press
3. LCD shows: "STEP 2/2: SCALE\nReading...\nPlease wait"
4. Read 20 HX711 samples → compute `scale = (reading - offset) / 500`
5. Validate: `scale ≠ 0`; if `scale == 0` → return (None, None) with "Invalid scale" error
6. Save to `calibration.json`: `{"offset": offset, "scale": scale}`
7. LCD displays: "Cal Complete!\nData saved\nOffset: X\nScale: Y.YY" (shows actual values for 3 seconds)

**During Monitoring:** Pressing CAL button triggers re-calibration with same step-by-step process.

### Network Modes in Detail

#### ONLINE MODE (WiFi Connected + Internet Reachable)
- Local alerts fully operational (LCD/LED/Buzzer/Buttons)
- SMS notifications enabled at all milestones and low-volume alerts
- LCD displays: `WiFi: OK  Mode: ONLINE`
- System sends status "OK" on Line 3

#### LOCAL-ONLY MODE (WiFi Unavailable or Internet Unreachable)
- All local alerts fully operational (LCD/LED/Buzzer/Buttons) - no degradation in safety
- SMS alerts disabled (no network access)
- LCD clearly indicates: `WiFi: OFF/OK  SMS: OFF` 
- When low-volume alert triggers in LOCAL-ONLY: Line 3 shows "LOW SMS:OFF" to indicate SMS not sent
- System continues monitoring normally without internet dependency
- Checked every 60 seconds; automatic recovery to ONLINE when internet returns

#### Internet Reachability Check (check_internet_available function at main.py:287-304)
1. Check WiFi association: `wlan.isconnected()`
2. Test Africa's Talking API with lightweight HTTP GET: `urequests.get(https://api.africastalking.com/version1/messaging)`
3. Both must succeed for ONLINE mode; any failure → LOCAL-ONLY
4. Timeout: 5 seconds (balances responsiveness vs network latency)

## Project-Specific Patterns & Implementation Details

### Logging System (logger.py)

**Custom MicroPython Logger** - Provides file-based logging compatible with Pico's limited resources.

**Log Levels:**
- `DEBUG` - Verbose diagnostic info (sensor ready, etc.)
- `INFO` - General operational events (boot, WiFi connect, SMS sends, milestones)
- `WARNING` - Non-critical issues (WiFi fail, low volume alert in LOCAL mode)
- `ERROR` - Recoverable errors (recalibration fail, sensor read timeout)
- `CRITICAL` - Fatal conditions (sensor fault, invalid calibration)

**Log Output:**
- File: `system.log` (max 50KB, rotates to `system.log.bak`)
- Format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`
- Example: `[2026-02-10 14:32:45] [INFO] WiFi connected successfully`
- Note: Uses `.log` extension for real hardware Pico deployment

**Usage in Code:**
```python
from logger import info, warning, error, critical, debug

info("System booting")
warning("WiFi connection failed")
error("Sensor fault: HX711 timeout")
critical("Invalid calibration data")
```

**Log Points in main.py:**
- Boot sequence: initialization, WiFi connection, mode detection
- Calibration: start, success/failure, values saved
- Monitoring: start, mode switches, button presses
- Alerts: low volume, 25%/50%/100% milestones, completion
- Errors: sensor faults, timeouts, invalid data

**Reading Logs:**
```python
from logger import read_log, clear_log
logs = read_log(50)  # Last 50 lines from system.log
clear_log()          # Clear log file
```

**Accessing Logs on Real Hardware (Pico):**
- Connect Pico via USB
- Check `system.log` file in Pico disk/file explorer
- Check `system.log.bak` for rotated/archived logs
- Use MicroPython REPL to read logs:

**Troubleshooting:**
- If `system.log` grows large, it automatically rotates
- Logging failures fall back to console (print) silently
- Use `logger.py` functions independently from main loop (non-blocking)

**Sensor Fault Conditions:**
1. `raw == None` → HX711 timeout (device not Ready within 1 second)
2. `grams < -50` → unusually negative (indicates calibration error)
3. `grams > FULL_BAG_ML + 500` → exceeds expected physical capacity

**Fault Response (main.py:490-501):**
- Immediately set `Buzzer.MODE_FAULT` (continuous tone)
- Display "Sensor fault" + error description on LCD
- Freeze monitoring loop (continue updating buzzer, but no new data processing)
- User must press TERM button to exit fault state or restart signal
- No automatic recovery—this ensures clinician awareness of equipment malfunction

**Validation After Calibration Load:**
```python
grams = (raw - offset) / scale
if grams < -50 or grams > FULL_BAG_ML + 500:
    # Trigger sensor fault
```

### Button Debouncing Pattern (DebouncedButton class at main.py:48-75)

**Design:** Hardware debounce via software state machine (30ms debounce window).

**Key Points:**
1. Only returns `True` on **rising edge** (0→1 state transition)
2. Requires stable state for 30ms before accepting new input
3. Prevents noise-triggered events (e.g., vibration, loose wiring)
4. `pressed()` method must be called every 50-100ms max for responsiveness

**Implementation:**
```python
class DebouncedButton:
    def pressed(self):
        now = utime.ticks_ms()
        state = self.read()
        if state != self._last_state:
            self._last_state = state
            self._last_change = now
        # Require stable for 30ms
        if utime.ticks_diff(now, self._last_change) > self.debounce_ms:
            if state != self._stable_state:
                self._stable_state = state
                if state == 1:  # Only trigger on press (0→1)
                    return True
        return False
```

**Usage in Monitoring Loop:**
```python
if btn_ack.pressed():
    alarm_silenced = True
if btn_new.pressed():
    # Reset counters, tare, restart monitoring
if btn_term.pressed():
    # Graceful shutdown
```

### Network Graceful Degradation

**Design Philosophy:** Network operations should NEVER block main loop or compromise local alerting.

**Implementation:**
1. SmsSender class wraps WiFi and SMS logic in `try/except`
2. WiFi connection happens at Boot (15s timeout) - only once
3. Internet test runs every 60s but has 5s timeout (non-blocking)
4. SMS send failures silently skip (logged implicitly by `send()` returning False)
5. `network` module is conditionally imported:
   ```python
   try:
       import network
       import urequests
   except ImportError:
       network = None
       urequests = None
   ```

**Graceful Handling:**
- If WiFi unavailable → `SmsSender.connected = False` → MODE_LOCAL_ONLY
- If SMS send fails → Continue monitoring (no exception raised)
- If API key invalid → SMS sends silently fail, local alerts continue
- System can run WITHOUT WiFi/SMS entirely for standalone monitoring

**Critical:** Never do `wlan.connect()` in the monitoring loop—only at boot.

### LCD Display Helper Pattern

**Function:** `lcd_line(lcd, line, text)` at main.py:177

```python
def lcd_line(lcd, line, text):
    lcd.putstr_at(text, line)
```

**Convention:**
- Line numbers: 0, 1, 2, 3 (0-indexed)
- Max 20 characters per line (padded by LCD driver)
- Always start fresh with `lcd.clear()` before updating full screen
- Partial updates (single line) use `lcd_line()` directly

**Example Display Update (Monitoring Loop, main.py:480-487):**
```python
lcd_line(lcd, 0, "Remain: %4d mL" % remaining)
lcd_line(lcd, 1, "Done:   %3d %%" % percent)
lcd_line(lcd, 2, "Delivered:%4d" % delivered)
mode_indicator = "OK" if mode == MODE_ONLINE else "LOCAL"
lcd_line(lcd, 3, "Status: %s" % mode_indicator)
```

### Configuration Hierarchy

**Priority (highest to lowest):**
1. Runtime state after `apply_secrets()` call
2. Values from `secrets.json` (keys: WIFI_SSID, WIFI_PASSWORD, SMS_USERNAME, SMS_RECIPIENTS, SMS_API_KEY)
3. Module-level default constants (main.py:32-36) - **all empty by default**

**Secrets Loading (apply_secrets function at main.py:331-342):**
```python
def apply_secrets():
    global WIFI_SSID, WIFI_PASSWORD, SMS_USERNAME, SMS_RECIPIENTS, SMS_API_KEY
    data = load_secrets_json()
    if not data:
        return
    WIFI_SSID = data.get("WIFI_SSID", WIFI_SSID)
    # ... other keys
```

**Fallback Behavior:**
- If `secrets.json` missing/invalid JSON → Use module defaults (empty values → LOCAL-ONLY mode)
- If any secret key missing → Use existing default value
- If `WIFI_SSID` empty string → WiFi connection skipped → MODE_LOCAL_ONLY
- **No sensitive data hardcoded** - all credentials must come from secrets.json

### Alarm State Management

**Key Variables:**
- `sms_flags` — Track which milestones/alerts have already triggered
- `alarm_silenced` — User-set flag via ACK button (temporary mute)
- `last_alarm` — Track last alarm mode for edge detection

**Flow:**
1. When alarm_mode changes → Reset `alarm_silenced = False` (new alert requires new ACK)
2. If `alarm_silenced` AND `alarm_mode != OFF` → Don't activate buzzer
3. Pressing ACK button → Set `alarm_silenced = True` (silent until next event change)
4. Pressing NEW button → Reset `alarm_silenced = False` AND clear all `sms_flags`

**Example (main.py:502-515):**
```python
if alarm_mode != last_alarm:
    alarm_silenced = False  # New alarm requires new ACK
    last_alarm = alarm_mode

if alarm_mode != Buzzer.MODE_OFF and not alarm_silenced:
    buzzer.set_mode(alarm_mode)
else:
    buzzer.set_mode(Buzzer.MODE_OFF)
```

### Memory Management

**Concern:** Pico W has limited RAM (~200KB). Long monitoring sessions can cause heap overflow.

**Solution:** `gc.collect()` called every 500ms in monitoring loop (main.py:530):
```python
buzzer.update()
gc.collect()
utime.sleep_ms(500)
```

**Impact:** Prevents garbage from accumulating; essential for multi-hour monitoring sessions.

### HX711 Read Averaging

**Pattern:** All raw reads use `hx.read_average(N)` with N=5 or higher:
- Calibration setup: `hx.read_average(15)` or `hx.read_average(20)` (more stable)
- Monitoring loop: `hx.read_average(5)` (balance speed vs noise)
- NEW button tare: `hx.read_average(15)` (stable re-tare)

**Timeout:** `hx.read_average()` internally calls `hx.read_raw(timeout_ms=1000)`
Returns `None` if no valid reading within 1 second → triggers sensor fault

## Testing & Development Approaches

### Local Testing (No Hardware)

**Wokwi Simulator - Simulation Mode:**
- Set `SIMULATION_MODE = True` in main.py (line 18)
- System will use **mock sensor values** instead of real HX711 readings
- Simulates IV delivery over ~60 seconds (1500 mL → 0 mL)
- Calibration uses preset values: `offset = -453021`,  `scale = 907`
- Useful for testing UI flow, alerts, and button logic without real sensor

**Wokwi Simulator - Real Sensor Mode:**
- Set `SIMULATION_MODE = False` (default)
- Requires HX711 properly wired to Pico in Wokwi
- Test actual sensor readings and calibration process
- May fail if Wokwi doesn't fully simulate HX711

### Calibration Testing

**Manual Calibration Procedure:**
1. Press CAL button in idle state
2. Ensure load cell is empty when prompted
3. Press CAL when ready (marks offset)
4. Place known 500g weight on load cell
5. Press CAL again (calculates scale factor)
6. Calibration saved to `calibration.json`

**Pre-populate Calibration (Skip Re-calibration):**
```json
{
  "offset": -453021,
  "scale": 1234.5
}
```
Create `calibration.json` with known offset/scale values to skip calibration at boot.

**Troubleshooting:**
- If `scale == 0` after calibration → indicates no weight change detected (hardware issue)
- If offset readings are floating-point NaN → sensor timeout (HX711 connection issue)

### Network Mode Testing

**LOCAL-ONLY Mode (No WiFi Scenario):**
1. Leave WiFi credentials empty or incorrect in `secrets.json`
2. System boots to LOCAL-ONLY mode
3. All local alerts work; SMS disabled

**LOCAL-ONLY Mode (WiFi OK, Internet Blocked):**
1. Connect to valid WiFi
2. Block internet (firewall rule, no internet provider, etc.)
3. System detects no internet → MODE_LOCAL_ONLY
4. LCD shows `WiFi: OK  SMS: OFF`

**Mode Switching Test:**
1. Start in LOCAL-ONLY
2. Restore internet connectivity
3. Wait up to 60 seconds (next internet test interval)
4. System should auto-switch to ONLINE
5. LCD mode indicator updates within 1 cycle (500ms)

**SMS Failure Testing:**
1. Provide invalid API key in `secrets.json`
2. System connects WiFi (shows ONLINE if internet OK otherwise)
3. SMS calls fail silently (checked by `try/except` in `sms.send()`)
4. Local alerts continue unaffected

### Hardware Integration Testing

**HX711 Connection Verification:**
1. Read raw value: `hx = HX711(26, 27); raw = hx.read_raw()`
2. If consistently returning `None` → timeout → check DOUT/SCK GPIO connections
3. If returning unrealistic values → check load cell wiring

**Button Press Verification:**
```python
btn = DebouncedButton(8)
while True:
    if btn.pressed():
        print("Button pressed")
    utime.sleep_ms(50)
```

**LCD Display Test:**
1. Power on → should display splash screen
2. Move through boot → should show WiFi/Mode status
3. Calibration screen should appear if no `calibration.json`
4. Monitoring screen should show all 4 lines with real-time updates

## Common Modifications & Extension Points

### Adding New Alert Thresholds

**Example: Add 75% milestone SMS**

1. Add 75% SMS flag to initialization:
   ```python
   sms_flags = {"start": False, "25": False, "50": False, "75": False, "100": False, "low": False}
   ```

2. Add SMS send logic in monitoring loop (after main.py:520):
   ```python
   if percent >= 75 and not sms_flags["75"]:
       if mode == MODE_ONLINE:
           sms.send("IV delivered 75%.")
       sms_flags["75"] = True
   ```

3. Thresholds are proportional to `FULL_BAG_ML`:
   - If FULL_BAG_ML = 1500: 75% = 1125 mL delivered
   - If FULL_BAG_ML = 2000: 75% = 1500 mL delivered

### Changing Alert Volume Levels

**Example: Lower low-volume threshold from 200mL to 150mL**

1. Update constant (main.py:18):
   ```python
   LOW_CRITICAL_ML = 150  # Was 200
   ```

2. Update warning range (main.py:19-20):
   ```python
   LOW_WARNING_MIN = 150  # Was 200
   LOW_WARNING_MAX = 249  # Adjusted to maintain 100mL width
   ```

3. SMS threshold (main.py:516):
   ```python
   if remaining <= 150:  # Update from 200
       lcd_line(lcd, 3, "Status: LOW")
       if mode == MODE_ONLINE and not sms_flags["low"]:
           sms.send("IV low volume (%d mL)." % remaining)
   ```

### Changing SMS API Provider (Africa's Talking → Twilio/Other)

**Steps:**
1. Replace `AfricaTalkingSMS` class (main.py:138-154):
   ```python
   class TwilioSMS:
       def __init__(self, account_sid, auth_token):
           self.account_sid = account_sid
           self.auth_token = auth_token
           self.endpoint = "https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json".format(account_sid)
       
       def send(self, message, recipients):
           # Implement Twilio API call
           pass
   ```

2. Update `secrets.json` keys:
   ```json
   {
     "SMS_ACCOUNT_SID": "your_twilio_sid",
     "SMS_AUTH_TOKEN": "your_twilio_token"
   }
   ```

3. Update SmsSender initialization (main.py:125):
   ```python
   # Before: self.sms = AfricaTalkingSMS(...)
   # After:
   self.sms = TwilioSMS(self.account_sid, self.auth_token)
   ```

### Adding New Buttons/Hardware

**Example: Add "Pause" button on GPIO11 (replace buzzer with GPIO13)**

1. Define new constants (main.py:37-38):
   ```python
   PIN_BUTTON_PAUSE = 11  # New button
   PIN_BUZZER = 13  # Moved from 11
   ```

2. Initialize button (main.py:360):
   ```python
   btn_pause = DebouncedButton(PIN_BUTTON_PAUSE)
   ```

3. Add handler in monitoring loop:
   ```python
   if btn_pause.pressed():
       buzzer.set_mode(Buzzer.MODE_OFF)
       # Pause logic here
   ```

### LCD Custom Screens

**Example: Add startup diagnostics screen**

```python
def show_diagnostics(lcd, hx, sms):
    lcd.clear()
    lcd_line(lcd, 0, "Diagnostics")
    
    # Test HX711
    test_read = hx.read_average(3)
    hx_status = "OK" if test_read is not None else "FAIL"
    lcd_line(lcd, 1, "HX711: %s" % hx_status)
    
    # Test Internet
    internet_ok = check_internet_available(sms)
    lcd_line(lcd, 2, "Internet: %s" % ("OK" if internet_ok else "FAIL"))
    
    # Test SMS (optional)
    lcd_line(lcd, 3, "Ready")
    utime.sleep(3)
```

Call in boot sequence after calibration:
```python
# After calibration success
show_diagnostics(lcd, hx, sms)
```

### Add Real-time Alarming Webhook (Beyond SMS)

**Example: POST to webhook on critical low volume**

1. Extend SmsSender or create new notifier class:
   ```python
   class WebhookNotifier:
       def __init__(self, webhook_url):
           self.webhook_url = webhook_url
       
       def notify_low_volume(self, remaining_ml):
           if not urequests:
               return False
           payload = {"remaining_ml": remaining_ml, "timestamp": utime.time()}
           try:
               urequests.post(self.webhook_url, json=payload)
               return True
           except:
               return False
   ```

2. Integrate in monitoring loop:
   ```python
   if remaining <= LOW_CRITICAL_ML and not sms_flags["low"]:
       webhook.notify_low_volume(remaining)
       sms_flags["low"] = True
   ```

### Modifying Calibration Weight

**Example: Change from 500g to 1kg reference weight**

1. Update constant (main.py:22):
   ```python
   CAL_WEIGHT_G = 1000  # Was 500
   ```

2. LCD will automatically display new value (main.py:229):
   ```python
   lcd_line(lcd, 0, "Place %dg" % CAL_WEIGHT_G)  # Now shows "Place 1000g"
   ```

**Note:** Physical calibration weight must match constant value.

## System Objectives & Use Cases

1. **Continuously measure** IV fluid volume using a load cell
2. **Convert weight data** into remaining volume and percentage delivered
3. **Display real-time** infusion status on an LCD screen
4. **Provide visual alerts** using LEDs and audible alerts using a buzzer
5. **Send SMS notifications** via Africa's Talking at predefined milestones:
   - 0% delivered (start)
   - 25% delivered
   - 50% delivered
   - 100% delivered (completion)
6. **Send immediate alert** when remaining volume falls below critical threshold (<200 mL)
7. **Allow nurses** to acknowledge alarms, restart monitoring for new IV bag, or terminate session safely

### Human Interaction & Safety Considerations

- **Alarms can be acknowledged** without stopping monitoring (ACK button)
- **System does NOT automatically restart** after IV completion
- **Nurse confirmation required** for new IV or termination (NEW/TERM buttons)
- **Clear START and END states** prevent unintended operation
- **Low power state handling**: Pico W continues operating with graceful degradation if battery backup unavailable
- **Sensor fault handling**: No automatic recovery—ensures clinician awareness of equipment malfunction
- **Dual-mode operation**: LOCAL-ONLY mode ensures monitoring continues even without internet/SMS

## Critical Notes for Safety & Reliability

1. **Do NOT modify FULL_BAG_ML** without updating alert thresholds proportionally
   - FULL_BAG_ML = 1500 is baseline; all thresholds (LOW_CRITICAL_ML, warning range, percentages) are derived from this
   - If changed to 2000mL, update LOW_CRITICAL_ML proportionally (e.g., to ~266mL for same 13% threshold)

2. **Calibration persistence is critical**—invalid calibration halts monitoring with sensor fault
   - `offset = None` or `scale = 0` triggers FAULT mode
   - No automatic recovery—user must retry calibration or restart device
   - Calibration must be done with EXACT 500g reference weight specified in CAL_WEIGHT_G

3. **SMS flags reset ONLY on NEW button press**—required to re-send alerts for new IV bag
   - Pressing ACK (acknowledge) does NOT reset flags
   - Only NEW button clears all flags: `sms_flags = {"start": False, "25": False, "50": False, "100": False, "low": False}`
   - This prevents duplicate alerts for same IV bag but allows fresh alerts on new bag

4. **Internet tests use 5s timeout** by design—balances responsiveness vs network latency
   - If internet test hangs >5s, system times out and switches to LOCAL-ONLY
   - Re-tested every 60s; auto-recovery when internet returns
   - Prevents main loop from blocking on slow/flaky networks

5. **MicroPython memory**: `gc.collect()` called every 500ms in monitoring loop
   - Prevents garbage heap from accumulating over multi-hour sessions
   - Pico W has ~200KB RAM; long sessions without GC lead to out-of-memory crashes
   - If memory errors occur, reduce averaging sample sizes or increase GC frequency

6. **WiFi connection happens ONLY at boot**—never in monitoring loop
   - Multiple `wlan.connect()` calls in loop cause instability and slowdown
   - Internet testing uses lightweight HTTP GET (5s timeout) instead of reconnection
   - This keeps main monitoring loop fast and responsive

7. **Sensor timeout is 1000ms per read attempt**
   - If HX711 doesn't respond within 1s → returns None → triggers FAULT
   - Check DOUT/SCK GPIO connections if consistently timing out
   - Multiple None readings in a row indicate hardware disconnection

8. **LCD display updates every 500ms** (main monitoring cycle)
   - User will see up to 500ms delay in reading updates
   - Safe for clinical use; acceptable for continuous monitoring
   - Faster updates (100ms) may cause flicker on slow LCD controllers

9. **Button debounce is 30ms** to prevent noise/vibration false triggers
   - Button presses must be polled at least every 100ms max (main loop does 500ms cycle)
   - Very fast button presses (taps <50ms) might be missed
   - Sustained presses (>100ms) will always register

10. **Mode switching can occur without user action**
    - If WiFi drops during ONLINE mode → auto-switches to LOCAL-ONLY within 1 cycle (500ms)
    - LCD status line updates immediately
    - SMS alerts stop; local alerts continue unaffected
    - Allows seamless operation in areas with spotty WiFi

## Software Environment & Dependencies

### MicroPython Firmware

The system runs on **MicroPython** firmware for Raspberry Pi Pico / Pico W.

### Required Libraries (`requirements.txt`)

**Core (built-in):**
- micropython (v1.19.1 or later)
- machine (GPIO, PWM, I2C)
- utime (timing)
- json (config file parsing)
- gc (garbage collection)

**Networking:**
- network (WiFi connectivity)
- urequests (HTTP requests for SMS API and internet testing)

**Hardware Drivers (included in this project):**
- hx711.py (load cell driver)
- i2c_lcd.py (I2C LCD display interface)
- lcd_api.py (LCD base class)
- logger.py (file-based logging system)

**Special Handling:**
- `network` and `urequests` are conditionally imported in main.py
- If unavailable, system gracefully falls back to LOCAL-ONLY mode
- No external pip packages needed for core functionality

### Configuration Files

**secrets.json (user-provided, NOT in repo):**
```json
{
  "WIFI_SSID": "your_wifi_network",
  "WIFI_PASSWORD": "your_wifi_password",
  "SMS_USERNAME": "iviotdemo",
  "SMS_RECIPIENTS": ["+254XXXXXXXXX"],
  "SMS_API_KEY": "your_africastalking_api_key"
}
```

**calibration.json (auto-generated after first calibration):**
```json
{
  "offset": -453021,
  "scale": 1234.5
}
```

## Quick Reference: Key Functions

| Function | Purpose | Called From |
|----------|---------|------------|
| `check_internet_available(sms)` | Verify WiFi + API reachability | Mode detection & periodic retest |
| `calibrate_with_button(hx, lcd, btn)` | Interactive calibration workflow | Boot & CAL button handler |
| `update_leds(led_red, led_yellow, led_green, remaining)` | Map volume to LED state | Monitoring loop |
| `compute_percent(delivered)` | Convert delivered_mL to 0-100% | Monitoring loop |
| `load_secrets_json()` | Load WiFi/SMS config from file | Startup |
| `apply_secrets()` | Apply secrets to global variables | Startup |
| `wait_for_press(button, timeout_s)` | Block until button or timeout | Calibration |
| `load_calibration()` | Load offset/scale from calibration.json | Boot |
| `save_calibration(offset, scale)` | Save calibration to file | After calibration |
| `lcd_line(lcd, line, text)` | Display text on specific LCD line | Throughout monitoring loop |

## Expected Outcomes

The completed system provides:

- **Reliable real-time IV monitoring** with continuous volume tracking
- **Reduced nurse workload** through automated alerts and notifications
- **Improved patient safety** with visual, audible, and remote notifications at critical thresholds
- **Clear START and END states** preventing unintended operation
- **Graceful degradation** with LOCAL-ONLY mode for offline capability
- **Scalable foundation** for future hospital IoT expansion
- **Clinical-grade reliability** with sensor fault detection and recovery procedures
