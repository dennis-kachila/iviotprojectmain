# IoT IV Fluid Monitoring System

Raspberry Pi Pico MicroPython-based IV fluid monitoring system with drop counting, prescription control, dual-sensor bubble detection, and SMS notifications via Africa's Talking API.

## Features

- **Prescription-based monitoring** - Nurse inputs target volume, duration, and drip factor via keypad
- **Drop counting** - Real-time drop detection using IR sensor
- **Dual-sensor bubble detection** - Requires both Bubble IR and Bubble Slot sensors to confirm (prevents false alarms)
- **Smart alerts** - LCD display, LEDs, and buzzer with priority-based alarm system
- **Milestone notifications** - Alerts at 0%, 25%, 50%, 100% of prescribed volume
- **No-flow detection** - Automatic detection of line occlusion or clamp closure
- **Time-elapsed monitoring** - Alert if prescribed time complete but volume incomplete
- **Dual-mode operation:**
  - **ONLINE MODE:** SMS notifications + local alerts (Wi-Fi + Internet verified)
  - **LOCAL-ONLY MODE:** Local alerts only (graceful degradation without internet)
- **4x3 Membrane Keypad** - Intuitive prescription entry interface
- **Button controls** - Acknowledge, New IV, Reset Counters, Terminate
- **Automatic network mode detection and recovery**

## Hardware Requirements

- Raspberry Pi Pico W (with wireless for SMS)
- **Drop IR Sensor** - Digital output module for drop counting
- **Bubble IR Sensor** - Digital output module for bubble detection
- **Bubble Slot Module** - LM393 optocoupler for bubble confirmation
- **4x3 Membrane Keypad** - Prescription input
- 20x4 I2C LCD (address 0x27)
- 3x LEDs (Red, Yellow, Green) with resistors
- 4x Push buttons with pull-down resistors
- Passive Buzzer (PWM capable)
- Breadboard and jumper wires

## GPIO Pin Mapping

| Component | GPIO Pin | Description |
|-----------|----------|-------------|
| **Buttons** | | |
| ACK Button | GPIO8 | Acknowledge/silence alarms |
| NEW Button | GPIO9 | Reset and re-enter prescription |
| TERM Button | GPIO10 | Terminate session |
| CAL Button | GPIO12 | Reset counters (keep prescription) |
| **Display & Audio** | | |
| I2C SDA | GPIO16 | LCD data line |
| I2C SCL | GPIO17 | LCD clock line |
| Buzzer | GPIO11 | Audible alerts (PWM) |
| **LEDs** | | |
| Red LED | GPIO18 | Critical/fault indicator |
| Yellow LED | GPIO19 | Warning level indicator |
| Green LED | GPIO20 | Normal operation indicator |
| **Sensors** | | |
| Drop IR | GPIO21 | Drop detection sensor |
| Bubble IR | GPIO22 | Bubble detection sensor 1 |
| Bubble Slot | GPIO26 | Bubble detection sensor 2 |
| **Keypad (4x3 Matrix)** | | |
| Row 1 | GPIO2 | Keypad row output |
| Row 2 | GPIO3 | Keypad row output |
| Row 3 | GPIO4 | Keypad row output |
| Row 4 | GPIO5 | Keypad row output |
| Column 1 | GPIO6 | Keypad column input |
| Column 2 | GPIO7 | Keypad column input |
| Column 3 | GPIO13 | Keypad column input |

## Software Setup

### 1. Install Dependencies

```bash
# Activate virtual environment (for development only)
.\.venv\Scripts\Activate.ps1

# All MicroPython dependencies are built-in
# No pip install needed for Pico deployment
```

### 2. Configure Secrets

Edit `secrets.json` with your credentials:

```json
{
  "WIFI_SSID": "your_wifi_ssid",
  "WIFI_PASSWORD": "your_wifi_password",
  "SMS_USERNAME": "iviotdemo",
  "SMS_RECIPIENTS": ["+254XXXXXXXXX"],
  "SMS_API_KEY": "your_africastalking_api_key"
}
```

### 3. Upload to Pico

Copy these files to the Pico:
- `main.py` - Main application
- `config.py` - Configuration constants
- `keypad.py` - Keypad driver
- `sensors.py` - Drop and bubble sensor drivers
- `i2c_lcd.py` - LCD driver
- `lcd_api.py` - LCD API
- `logger.py` - Logging system
- `secrets.json` - WiFi/SMS credentials

## Prescription Input Flow

1. **Enter Volume** - Target volume in mL (1-1500)
2. **Enter Duration** - Infusion time in minutes (1-1440)
3. **Enter Drip Factor** - gtt/mL (or press * for default 20)
4. **System calculates** - Required drip rate displayed
5. **Monitoring starts** - Drop counting begins

### Keypad Layout
```
1 2 3
4 5 6
7 8 9
* 0 #
```
- `#` = Confirm/Enter
- `*` = Backspace or Use Default

## Network Connectivity & SMS Modes

### ONLINE Mode
- **When:** Wi-Fi connected AND internet/API reachable
- **Features:** Local alerts + SMS notifications enabled
- **LCD Display:** `ONLINE  SMS ON`
- **SMS Alerts:** Start, milestones (25%, 50%, 100%), low-volume, bubble, no-flow

### LOCAL-ONLY Mode
- **When:** Wi-Fi unavailable OR internet unreachable
- **Features:** All local monitoring continues (LCD/LED/Buzzer); SMS disabled
- **LCD Display:** `LOCAL ONLY SMS OFF`
- **SMS Alerts:** Automatically skipped; alerts continue locally

### Auto-Recovery
- System checks internet connectivity every 60 seconds
- Automatically switches to ONLINE mode when internet returns
- Nurse can see mode change on LCD immediately

## Usage

### Starting a New Infusion

1. **Power on** the system
2. **Network check** - System tests WiFi and internet
3. **Prescription entry:**
   - Enter target volume (mL)
   - Enter duration (minutes)
   - Enter drip factor or use default
4. **Monitoring begins** - System displays calculated drip rate
5. **Drop counting starts** - Real-time monitoring active

### During Monitoring

- **ACK Button (GPIO8)**: Silence buzzer (monitoring continues)
- **NEW Button (GPIO9)**: Full reset, re-enter prescription for new IV bag
- **CAL Button (GPIO12)**: Reset counters only, keep current prescription
- **TERM Button (GPIO10)**: End monitoring session safely

### LED Indicators

- **Green**: Normal operation (≥300 mL remaining)
- **Yellow**: Warning level (200-299 mL remaining)
- **Red**: Critical low (<200 mL) or bubble/fault detected

### Buzzer Patterns

- **Fast beeping (100ms)**: Bubble detected (highest priority)
- **Medium beeping (150ms)**: Low IV volume
- **Slow beeping (200ms)**: No flow / occlusion
- **Continuous tone**: Completion or fault state

### SMS Notifications (ONLINE Mode Only)

Automatic SMS alerts sent at:
- **Start**: "IV monitoring started: Xml over Ymin (0% delivered)"
- **25%**: "IV delivered 25%."
- **50%**: "IV delivered 50%."
- **100%**: "IV completed 100%."
- **Low volume**: "IV low volume (X mL)."
- **Bubble**: "BUBBLE DETECTED - CHECK IV LINE"
- **No flow**: "NO FLOW - Check IV line (X mL delivered)"
- **Time elapsed**: "TIME ELAPSED - Volume incomplete: XmL/YmL"

## Alert Priority System

1. **Bubble detected** (highest) - Immediate action required
2. **No flow / occlusion** - Check IV line
3. **Low volume** - Prepare new bag
4. **Time elapsed** - Rate adjustment needed
5. **Completion** - Normal end state

## Alarm States

### Bubble Alarm
- **Trigger**: Both Bubble IR AND Bubble Slot detect bubble within 400ms
- **Display**: "** BUBBLE DETECTED **"
- **Action**: Check IV line, press ACK to acknowledge

### No-Flow Alarm
- **Trigger**: No drops detected for 30 seconds (before completion)
- **Display**: "** NO FLOW **"
- **Action**: Check line clamp, press ACK to continue

### Low Volume Alert
- **Trigger**: Remaining volume < 200 mL
- **Display**: "LOW VOLUME ALERT" or "LOW VOL SMS:OFF"
- **Action**: Prepare replacement bag

### Time Elapsed Alert
- **Trigger**: Prescribed time complete but volume incomplete
- **Display**: "** TIME ELAPSED ** Volume incomplete"
- **Action**: Verify flow rate, consider adjustment

## Project Structure

```
.
├── main.py                    # Main application with state machine
├── config.py                  # System configuration constants
├── keypad.py                  # 4x3 keypad driver
├── sensors.py                 # Drop and bubble sensor drivers
├── lcd_api.py                 # LCD base API
├── i2c_lcd.py                 # I2C LCD implementation
├── logger.py                  # File-based logging system
├── secrets.json               # WiFi/SMS credentials (not in git)
├── diagram.json               # Wokwi simulation diagram
├── wokwi.toml                 # Wokwi configuration
├── requirements.txt           # Dependencies documentation
├── modifications.md           # Design specification
├── IMPLEMENTATION_SUMMARY.md  # Change documentation
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## Wokwi Simulation

1. Open VS Code
2. Open `diagram.json` (note: needs update for new sensors)
3. Click "Start Simulation" in the Wokwi extension
4. Interact with buttons, keypad, and sensors in the simulator

## Configuration Constants

Edit these in `config.py`:

```python
# Prescription defaults
DEFAULT_DRIP_FACTOR = 20        # gtt/mL
MAX_VOLUME_ML = 1500            # Maximum volume
MAX_DURATION_MIN = 1440         # Maximum duration (24 hours)

# Sensor timing
DROP_DEBOUNCE_MS = 80           # Drop detection debounce
DROP_CONFIRM_TIMEOUT_SEC = 30   # No-drop timeout
BUBBLE_CONFIRM_WINDOW_MS = 400  # Bubble dual-sensor window

# Thresholds
LOW_VOLUME_THRESHOLD_ML = 200
WARNING_VOLUME_THRESHOLD_ML = 300
```

## Troubleshooting

### Sensor Issues
**Drop sensor not counting:**
- Check Drop IR sensor wiring to GPIO21
- Verify sensor output is 3.3V compatible
- Test with manual drop simulation
- Check debounce timing (80ms)

**Bubble false alarms or missed detections:**
- Verify both Bubble IR (GPIO22) AND Bubble Slot (GPIO26) connected
- System requires BOTH sensors to confirm within 400ms
- Check sensor alignment with IV tubing
- Verify 3.3V power supply to sensors

### Keypad Not Responding
- Check row pins: GPIO2, 3, 4, 5
- Check column pins: GPIO6, 7, 13
- Verify pull-down resistors on columns
- Test individual keys with multimeter

### LCD Not Displaying
- Check I2C address (default 0x27)
- Verify SDA → GPIO16, SCL → GPIO17
- Test I2C connection with scanner
- Check 5V power to LCD backlight

### SMS Not Sending
- Verify Wi-Fi credentials in `secrets.json`
- Check Africa's Talking API key and username
- Ensure recipient numbers include country code (+254...)
- System will continue in LOCAL-ONLY mode if SMS fails

### Prescription Input Issues
- Ensure values within valid ranges:
  - Volume: 1-1500 mL
  - Duration: 1-1440 minutes
  - Drip factor: Use common values (10, 15, 20, 60) or press * for default
- Press # to confirm each entry
- Press * to backspace

## Migration from Load Cell Version

If upgrading from the old weight-based system:

1. **Hardware changes:**
   - Remove HX711 and load cell
   - Install Drop IR sensor (GPIO21)
   - Install Bubble IR sensor (GPIO22)
   - Install Bubble Slot module (GPIO26)
   - Install 4x3 keypad matrix

2. **Software:**
   - Old `main_old.py` preserved in git history
   - No calibration file needed
   - Update Wokwi `diagram.json`

3. **Workflow changes:**
   - Nurse must enter prescription via keypad
   - Monitoring now prescription-based (not fixed 1500mL)
   - Dual-sensor bubble detection prevents false alarms

## Documentation

- **[modifications.md](modifications.md)** - Complete design specification
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Implementation details and changes
- **[config.py](config.py)** - All configuration constants
- **[.github/copilot-instructions.md](.github/copilot-instructions.md)** - Comprehensive system documentation

## License

See project documentation for details.

## Credits

Developed for IoT-based healthcare monitoring applications.
Drop counting and prescription control redesign - February 2026.
