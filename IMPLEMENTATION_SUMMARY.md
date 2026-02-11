# Implementation Summary: Drop Counting & Bubble Detection System

## Overview

The IV monitoring system has been completely redesigned from a **weight-based (load cell)** system to a **drop-counting prescription-controlled** system with **dual-sensor bubble detection**.

---

## What Was Changed

### 1. **Removed Components**
- ❌ HX711 24-bit ADC and load cell sensor
- ❌ Weight-based volume measurement
- ❌ Calibration system (offset/scale for load cell)
- ❌ Fixed 1500mL bag assumption
- ❌ `hx711.py` driver module
- ❌ `calibration.json` file

### 2. **Added Components**

#### Hardware:
- ✅ **Drop IR Sensor** (GPIO21) - Counts individual drops
- ✅ **Bubble IR Sensor** (GPIO22) - Bubble detection sensor 1
- ✅ **Bubble Slot Module** (GPIO26) - Bubble detection sensor 2
- ✅ **4x3 Membrane Keypad** - Prescription input
  - Rows: GPIO2, GPIO3, GPIO4, GPIO5
  - Columns: GPIO6, GPIO7, GPIO13

#### Software Modules:
- ✅ **keypad.py** - 4x3 keypad scanning and input buffering
- ✅ **sensors.py** - Drop sensor and bubble detector classes
- ✅ **config.py** - All system constants and configuration

### 3. **Modified Components**
- ✅ **main.py** - Complete rewrite with new state machine
- ✅ **requirements.txt** - Updated module list
- ⚠️ **diagram.json** - Needs manual update in Wokwi (see below)

---

## New System Features

### Prescription Input Flow
1. **Enter Target Volume** (1-1500 mL)
2. **Enter Duration** (1-1440 minutes)
3. **Enter Drip Factor** (optional, default: 20 gtt/mL)
4. System calculates required drip rate (gtt/min)

### Drop Counting Logic
- Single source of truth: **Drop IR sensor**
- Debounced edge detection (80ms minimum between drops)
- Sliding 60-second window for rate calculation
- Real-time calculation of:
  - Delivered volume (drops ÷ drip_factor)
  - Remaining volume (target - delivered)
  - Percentage delivered (0-100% relative to prescription)
  - Measured flow rate (gtt/min and mL/hr)
  - Estimated time remaining (ETA)

### Dual-Sensor Bubble Detection
- **Bubble confirmed ONLY if BOTH sensors trigger within 400ms**
- Prevents false alarms from single sensor noise
- Highest priority alarm (overrides all other alerts)
- SMS notification: "BUBBLE DETECTED - CHECK IV LINE"

### Prescription-Based Milestones
- Alerts at: **0%, 25%, 50%, 100%** of prescribed volume
- Low volume alert: < 200 mL remaining
- Time-elapsed alert: Duration complete but volume incomplete
- No-flow alert: No drops for 30 seconds

### Enhanced Button Controls
- **Acknowledge (GPIO8)** - Silence buzzer (monitoring continues)
- **New IV (GPIO9)** - Full reset, re-enter prescription
- **Calibration (GPIO12)** - Reset counters only, keep prescription
- **Terminate (GPIO10)** - Clean shutdown

---

## GPIO Pin Mapping

| Component | GPIO Pin | Notes |
|-----------|----------|-------|
| **Buttons** | | |
| Acknowledge | GPIO8 | Silence alarm |
| New IV | GPIO9 | Reset & re-enter prescription |
| Terminate | GPIO10 | End session |
| Calibration | GPIO12 | Reset counters |
| **LEDs** | | |
| Red LED | GPIO18 | Critical/fault (<200mL) |
| Yellow LED | GPIO19 | Warning (200-299mL) |
| Green LED | GPIO20 | Normal (≥300mL) |
| **Audio** | | |
| Buzzer | GPIO11 | PWM alarm |
| **Display** | | |
| I2C SDA | GPIO16 | LCD data |
| I2C SCL | GPIO17 | LCD clock |
| **Sensors** | | |
| Drop IR | GPIO21 | **NEW** - Drop counter |
| Bubble IR | GPIO22 | **NEW** - Bubble detect 1 |
| Bubble Slot | GPIO26 | **NEW** - Bubble detect 2 |
| **Keypad** | | |
| Row 1 | GPIO2 | **NEW** - Keypad row |
| Row 2 | GPIO3 | **NEW** - Keypad row |
| Row 3 | GPIO4 | **NEW** - Keypad row |
| Row 4 | GPIO5 | **NEW** - Keypad row |
| Column 1 | GPIO6 | **NEW** - Keypad column |
| Column 2 | GPIO7 | **NEW** - Keypad column |
| Column 3 | GPIO13 | **NEW** - Keypad column |

---

## State Machine Changes

### New States:
- `STATE_PRESCRIPTION_INPUT` - Keypad entry of prescription
- `STATE_BUBBLE_ALARM` - Dual-sensor bubble confirmed
- `STATE_NO_FLOW` - No drops for 30s (before completion)
- `STATE_TIME_ELAPSED` - Time complete but volume incomplete

### Updated States:
- `STATE_MONITORING` - Now tracks drops, not weight
- `STATE_COMPLETE` - Volume delivered OR no-flow at target

### Removed States:
- Calibration state (no longer needed)
- Weight tare/offset states

---

## Configuration Constants (config.py)

```python
# Prescription defaults
DEFAULT_DRIP_FACTOR = 20 (gtt/mL)
MAX_VOLUME_ML = 1500
MAX_DURATION_MIN = 1440

# Sensor timing
DROP_DEBOUNCE_MS = 80
DROP_CONFIRM_TIMEOUT_SEC = 30
BUBBLE_CONFIRM_WINDOW_MS = 400

# Thresholds
LOW_VOLUME_THRESHOLD_ML = 200
WARNING_VOLUME_THRESHOLD_ML = 300
MILESTONES = [0, 25, 50, 100]

# Network
NETWORK_RECHECK_SEC = 60
```

---

## LCD Display Format

### During Monitoring:
```
VOL 075/120 mL      (delivered/target)
% 62  Rem 45mL       (percentage, remaining)
Rate 28gtt  25mLh    (measured rate)
ONLINE  SMS ON       (mode status)
```

### During Alarms:
- Bubble: `** BUBBLE DETECTED ** / CHECK IV LINE!`
- No Flow: `** NO FLOW ** / Check line/clamp`
- Time Elapsed: `** TIME ELAPSED ** / Volume incomplete`
- Complete: `INFUSION COMPLETE / 100%`

---

## SMS Alerts (ONLINE Mode)

Sent via Africa's Talking when internet available:
1. **0%** - "IV monitoring started: 120mL over 60min (0% delivered)."
2. **25%** - "IV delivered 25%."
3. **50%** - "IV delivered 50%."
4. **100%** - "IV completed 100%."
5. **Low Volume** - "IV low volume (45 mL)."
6. **Bubble** - "BUBBLE DETECTED - CHECK IV LINE"
7. **No Flow** - "NO FLOW - Check IV line (75mL delivered)"
8. **Time Elapsed** - "TIME ELAPSED - Volume incomplete: 75mL/120mL"

---

## Calculations

### From Prescription:
```python
# Required drip rate
gtt_per_min_target = (target_volume_ml * drip_factor) / duration_minutes

# Prescribed flow rate
mL_per_hr_prescribed = (target_volume_ml / duration_minutes) * 60
```

### From Drop Sensor:
```python
# Delivered volume
delivered_ml = total_drops / drip_factor

# Percentage
percent_delivered = (delivered_ml / target_volume_ml) * 100

# Measured rate
drops_per_min = drops_in_last_60_seconds
mL_per_hr_measured = (drops_per_min * 60) / drip_factor

# ETA
eta_hours = remaining_ml / mL_per_hr_measured
```

---

## Files Changed

### New Files:
- `keypad.py` (208 lines) - Keypad scanning and input
- `sensors.py` (202 lines) - Drop and bubble sensors
- `config.py` (87 lines) - Configuration constants
- `main_old.py` (652 lines) - Backup of original main.py

### Modified Files:
- `main.py` (1050+ lines) - Complete rewrite
- `requirements.txt` - Updated module list

### Deleted Files:
- `hx711.py` - Load cell driver (no longer needed)
- `calibration.json` - Calibration data (if existed)

### Unchanged Files:
- `i2c_lcd.py` - LCD driver (still used)
- `lcd_api.py` - LCD API (still used)
- `logger.py` - Logging system (still used)
- `secrets.json` - WiFi/SMS credentials (still used)

---

## Testing Checklist

### Hardware Connections:
- [ ] Drop IR sensor connected to GPIO21
- [ ] Bubble IR sensor connected to GPIO22
- [ ] Bubble Slot module connected to GPIO26
- [ ] 4x3 Keypad connected (rows: 2,3,4,5 / cols: 6,7,13)
- [ ] All buttons, LEDs, buzzer, LCD properly connected

### Functional Tests:
- [ ] Keypad input working (digits, #, *)
- [ ] Prescription entry flow complete
- [ ] Drop sensor counting drops correctly
- [ ] Dual bubble detection working (both sensors required)
- [ ] Milestones triggering at correct percentages
- [ ] Low volume alert at < 200 mL remaining
- [ ] No-flow detection after 30s no drops
- [ ] Time-elapsed warning if duration complete
- [ ] SMS alerts sending (ONLINE mode)
- [ ] Local-only mode working without internet
- [ ] Buttons: ACK, NEW, CAL, TERM functioning

### Edge Cases:
- [ ] Empty prescription entry (validation)
- [ ] Invalid volume/duration values
- [ ] Single bubble sensor trigger (should NOT alarm)
- [ ] Flow resuming after no-flow alarm
- [ ] Network reconnection during monitoring
- [ ] Completion with exact volume delivered

---

## Wokwi Diagram Update Required ⚠️

The `diagram.json` file still contains the old HX711 load cell circuit. You need to:

1. **Remove** HX711 component
2. **Add** Drop IR sensor (GPIO21)
3. **Add** Bubble IR sensor (GPIO22)
4. **Add** Bubble Slot module (GPIO26)
5. **Add** 4x3 Keypad matrix (7 GPIOs)
6. **Update** all wire connections

**Recommendation:** Use Wokwi visual editor to rebuild the circuit diagram rather than manually editing JSON.

---

## Migration Notes

### For Existing Deployments:
1. Backup old code (already done - see `main_old.py`)
2. Update hardware: Remove load cell, install sensors + keypad
3. Update wiring per new GPIO map
4. Flash new code to Pico W
5. Test prescription input flow before clinical use
6. Verify dual bubble detection with test bubbles
7. Confirm SMS alerts working in ONLINE mode

### Backward Compatibility:
- ❌ **NOT compatible** with old weight-based system
- ❌ Old `calibration.json` files will be ignored/deleted
- ✅ `secrets.json` format unchanged (WiFi/SMS)
- ✅ LCD, LEDs, Buzzer, Buttons use same GPIOs

---

## Known Limitations

1. **Drip factor must be known** - Nurse must input or use default
2. **Bubble detection requires both sensors** - Single sensor won't trigger
3. **No automatic catch-up SMS** - Missed alerts during offline won't resend
4. **Fixed debounce time** - 80ms may need tuning for different drop speeds
5. **No historical data storage** - Only current session metrics

---

## Next Steps

1. ✅ Code implementation complete
2. ⚠️ **Update Wokwi diagram.json** (manual required)
3. ⚠️ **Hardware assembly** with new sensors
4. ⚠️ **Physical testing** with actual IV set
5. ⚠️ **Clinical validation** before deployment

---

## Support & Documentation

- See [modifications.md](modifications.md) for full design specification
- See [README.md](README.md) for system overview (needs update)
- See [PROJECT_REPORT.md](PROJECT_REPORT.md) for project details (needs update)
- Old system preserved in `main_old.py` for reference

---

**Branch:** `feature/sensor-drip-bubble-detection`  
**Commit:** Major redesign with drop counting and dual-sensor bubble detection  
**Status:** ✅ Code complete, ⚠️ Hardware testing pending
