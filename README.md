# IoT IV Fluid Monitoring System

Raspberry Pi Pico MicroPython-based IV fluid monitoring system with HX711 load cell, I2C LCD display, visual/audible alerts, and SMS notifications via Africa's Talking API.

## Features

- Real-time IV fluid volume monitoring using load cell (HX711)
- 20x4 I2C LCD display showing remaining volume, percentage delivered, and status
- Visual indicators (Red/Yellow/Green LEDs) based on fluid levels
- Audible alerts via buzzer with different patterns for different states
- **Dual-mode operation:**
  - **ONLINE MODE:** SMS notifications + local alerts (Wi-Fi + Internet verified)
  - **LOCAL-ONLY MODE:** Local alerts only (graceful degradation without internet)
- SMS notifications at 0%, 25%, 50%, 100%, and low volume threshold (ONLINE mode)
- Guided calibration process with dedicated button
- Button controls for acknowledgment, new IV bag, termination, and calibration
- Automatic network mode detection and recovery

## Hardware Requirements

- Raspberry Pi Pico / Pico W
- HX711 24-bit ADC with load cell (5kg)
- 20x4 I2C LCD (address 0x27)
- 3x LEDs (Red, Yellow, Green) with 1kΩ resistors
- 4x Push buttons
- Buzzer (PWM capable)
- Breadboard and jumper wires

## GPIO Pin Mapping

| Component | GPIO Pin | Description |
|-----------|----------|-------------|
| ACK Button | GPIO8 | Acknowledge/silence alarms |
| NEW Button | GPIO9 | Start monitoring new IV bag |
| TERM Button | GPIO10 | Terminate session |
| CAL Button | GPIO12 | Start calibration process |
| Buzzer | GPIO11 | Audible alerts (PWM) |
| I2C SDA | GPIO16 | LCD data line |
| I2C SCL | GPIO17 | LCD clock line |
| Red LED | GPIO18 | Critical low volume indicator |
| Yellow LED | GPIO19 | Warning level indicator |
| Green LED | GPIO20 | Normal operation indicator |
| HX711 DT | GPIO26 | Load cell data |
| HX711 SCK | GPIO27 | Load cell clock |

## Software Setup

### 1. Install Dependencies

```bash
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
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

- Copy all `.py` files to the Pico
- Copy `secrets.json` to the Pico
- Ensure `main.py` is in the root directory

## Network Connectivity & SMS Modes

### ONLINE Mode
- **When:** Wi-Fi connected AND internet/API reachable
- **Features:** Local alerts + SMS notifications enabled
- **LCD Display:** `Mode: ONLINE`
- **SMS Alerts Sent:** Start (0%), 25%, 50%, 100%, low-volume

### LOCAL-ONLY Mode
- **When:** Wi-Fi unavailable OR internet unreachable
- **Features:** All local monitoring continues (LCD/LED/Buzzer); SMS disabled
- **LCD Display:** `Mode: LOCAL ONLY` or `WiFi: OFF/OK  SMS: OFF`
- **SMS Alerts:** Automatically skipped with "SMS: OFF" indicator

### Auto-Recovery
- System checks internet connectivity every 60 seconds
- Automatically switches to ONLINE mode when internet returns
- Nurse can see mode change on LCD display

## Usage

### Initial Setup

1. Power on the system
2. System will check for existing calibration
3. If no calibration exists, follow on-screen prompts:
   - Remove all weight from load cell
   - Press CAL button to tare
   - Place 500g calibration weight
   - Press CAL button to complete

### During Monitoring

- **ACK Button**: Silence buzzer without stopping monitoring
- **NEW Button**: Reset and start monitoring a new IV bag (auto-tares)
- **TERM Button**: End monitoring session and power down
- **CAL Button**: Recalibrate the load cell at any time

### LED Indicators

- **Green**: Normal operation (300-1500 mL remaining)
- **Yellow**: Warning level (200-299 mL remaining)
- **Red**: Critical low (<200 mL remaining)

### Buzzer Patterns

- **Fast beeping (150ms)**: Low IV volume
- **Slow beeping (600ms)**: IV complete (100%)
- **Continuous tone**: Sensor fault

### SMS Notifications

Automatic SMS alerts are sent at:
- Monitoring start (0% delivered)
- 25% delivered
- 50% delivered
- 100% delivered (complete)
- Low volume threshold (<200 mL)

## Project Structure

```
.
├── main.py              # Main application logic
├── hx711.py             # HX711 load cell driver
├── lcd_api.py           # LCD base API
├── i2c_lcd.py           # I2C LCD implementation
├── secrets.py           # Configuration template (fallback)
├── secrets.json         # Actual configuration (not in git)
├── calibration.json     # Calibration data (auto-generated)
├── diagram.json         # Wokwi simulation diagram
├── wokwi.toml           # Wokwi configuration
├── requirements.txt     # Python dependencies
├── .gitignore           # Git ignore rules
├── Instructions.md      # Detailed project specification
└── README.md            # This file
```

## Wokwi Simulation

1. Open VS Code
2. Open `diagram.json`
3. Click "Start Simulation" in the Wokwi extension
4. Interact with buttons and load cell in the simulator

## Configuration Constants

Edit these in `main.py` if needed:

- `FULL_BAG_ML = 1500` - Maximum IV bag volume in mL
- `LOW_CRITICAL_ML = 200` - Critical low volume threshold
- `CAL_WEIGHT_G = 500` - Calibration weight in grams

## Troubleshooting

### Sensor Fault Errors
- Check HX711 wiring (DT → GPIO26, SCK → GPIO27)
- Ensure load cell is properly connected to HX711
- Verify power supply is stable

### LCD Not Displaying
- Check I2C address (default 0x27)
- Verify SDA → GPIO16, SCL → GPIO17
- Test I2C connection with scanner

### SMS Not Sending
- Verify Wi-Fi credentials in `secrets.json`
- Check Africa's Talking API key and username
- Ensure recipient numbers include country code (+254...)

### Calibration Issues
- Use a known accurate weight (500g recommended)
- Ensure stable surface without vibrations
- Press CAL button at each step as prompted

## License

See project documentation for details.

## Credits

Developed for IoT-based healthcare monitoring applications.
