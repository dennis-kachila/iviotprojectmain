
# Comprehensive Project Description and Implementation Guide

## IoT-Based IV Fluid Monitoring and Alert System

---

## 1. Project Overview

This project implements an **IoT-based intravenous (IV) fluid monitoring system** designed to assist nurses and clinicians by continuously monitoring the volume of IV fluid delivered to a patient and providing **visual, audible, and SMS alerts** at critical stages of infusion.

The system uses a **load cell sensor** interfaced through an **HX711 24-bit ADC** to measure the weight of an IV fluid bag. The measured weight is converted into remaining fluid volume (in milliliters) and percentage delivered. A **Raspberry Pi Pico / Pico W** acts as the main controller, managing sensing, computation, display, alerts, and wireless communication.

The system supports **human-in-the-loop control** through push buttons, ensuring safe operation aligned with clinical workflows. The monitoring process has a clearly defined **START**, **CONTINUOUS MONITORING**, and **END/TERMINATION** state.

---

## 2. Hardware Requirements and Bill of Materials

### 2.1 Main Microcontroller
- **Raspberry Pi Pico W** or **Pico WH** (with wireless capability for SMS)

### 2.2 Sensors and Measurement
- **Load Cell:** 5kg scale analog load cell
- **HX711 24-bit ADC Amplifier Module:** for load cell signal conditioning

### 2.3 User Interface
- **20x4 I2C LCD Display** (I2C address 0x27)
- **4x Push Buttons:** 
  - Acknowledge (GPIO8)
  - New IV (GPIO9)
  - Terminate (GPIO10)
  - Calibration (GPIO12)

### 2.4 Alerts and Indicators
- **3x LEDs:**
  - Red LED (GPIO18) — Critical low volume
  - Yellow LED (GPIO19) — Warning level
  - Green LED (GPIO20) — Normal operation
- **Passive Buzzer:** PWM-driven (GPIO11)

### 2.5 Passive Components
- **Resistors:**
  - 1kΩ resistors (×7) — LED current limiting
  - 10kΩ resistors (×4) — Button pull-down
- **Breadboard and jumper wires**
- **USB power supply** (5V, 2A minimum for Pico W)

---

## 2. System Objectives

1. Continuously measure IV fluid volume using a load cell.
2. Convert weight data into remaining volume and percentage delivered.
3. Display real-time infusion status on an LCD screen.
4. Provide visual alerts using LEDs and audible alerts using a buzzer.
5. Send SMS notifications via Africa’s Talking at predefined milestones:

   * 0% delivered (start)
   * 25% delivered
   * 50% delivered
   * 100% delivered (completion)
6. Send an immediate alert when the remaining volume falls below a critical threshold.
7. Allow nurses to acknowledge alarms, restart monitoring for a new IV bag, or terminate the session safely.

---

## 3. Hardware Interface and GPIO Mapping

### 3.1 Push Buttons (User Interaction)

| GPIO   | Mode              | Function                                          |
| ------ | ----------------- | ------------------------------------------------- |
| GPIO8  | Input (pull-down) | Reset / acknowledge alarms and silence buzzer     |
| GPIO9  | Input (pull-down) | New IV / restart monitoring after bag replacement |
| GPIO10 | Input (pull-down) | Power / terminate monitoring session              |
| GPIO12 | Input (pull-down) | Calibration / guided calibration process          |

* Buttons are **active HIGH**
* Software debounce of 20–50 ms is required
* Button presses override alarms but do not disable sensing unless explicitly terminating

---

### 3.2 Audible Alert

| GPIO   | Mode         | Function               |
| ------ | ------------ | ---------------------- |
| GPIO11 | Output (PWM) | Passive Buzzer driver  |

**Buzzer Type:** Passive Buzzer (requires PWM frequency to generate sound)

Buzzer patterns:

* Fast beeping (150ms) → Low IV volume
* Slow beeping (600ms) → IV complete
* Continuous tone (2kHz) → Sensor fault

---

### 3.3 LCD Display (I2C)

**Hardware:** 20x4 Character LCD with I2C Interface (Address: 0x27)

| GPIO   | Mode     | Function  |
| ------ | -------- | --------- |
| GPIO16 | I2C0 SDA | LCD data  |
| GPIO17 | I2C0 SCL | LCD clock |

Displayed information includes:

* Line 1: Remaining volume (mL)
* Line 2: Percentage delivered (%)
* Line 3: Total delivered volume (mL)
* Line 4: System status messages (OK, LOW, DONE, etc.)

The 20-character width allows detailed status display without scrolling.

---

### 3.4 Visual Indicators (LEDs)

| GPIO   | LED Color | Function                               |
| ------ | --------- | -------------------------------------- |
| GPIO18 | Red       | Critical low volume (<200 mL) or fault |
| GPIO19 | Yellow    | Warning level (200–299 mL)             |
| GPIO20 | Green     | Normal operation (300–1500 mL)         |

* Only one LED is active at a time
* LED blinking rate may increase as infusion nears completion

---

### 3.5 Load Cell Interface (HX711 Amplifier)

**Sensor:** 5kg Load Cell
**Amplifier:** HX711 24-bit ADC Module

| GPIO   | Signal      | Function              |
| ------ | ----------- | --------------------- |
| GPIO26 | HX711 DT    | Data output (DOUT)    |
| GPIO27 | HX711 SCK   | Serial clock (SCK)    |
| —      | HX711 VCC   | 5V power supply       |
| —      | HX711 GND   | Ground                |

**Signal Flow:** Load Cell → HX711 → GPIO26/27 (SPI protocol)

* Sampling interval: ~1 second (5 readings averaged per cycle)
* Digital filtering applied before calculations
* Offset and scale factor stored in `calibration.json`

---

## 4. Software Environment and Dependencies

### 4.1 MicroPython Environment

The system runs on **MicroPython** firmware for Raspberry Pi Pico / Pico W.

### 4.2 Required Libraries (`requirements.txt`)

**Core (built-in):**

* micropython
* machine
* time / utime
* uasyncio
* network
* json
* gc

**Networking:**

* urequests

**Hardware Drivers (external):**

* hx711
* lcd_api
* i2c_lcd

**Optional:**

* logging

These libraries support hardware access, concurrency, Wi-Fi networking, HTTP requests, and peripheral drivers.

---

## 5. Algorithmic Flow (Aligned with Flowchart)

### 5.1 Start and Initialization Phase

1. System powers ON.
2. Microcontroller initializes:

   * GPIO pins
   * HX711 interface
   * LCD display
   * LEDs and buzzer
   * Push buttons
3. LCD displays system boot and self-test status.
4. Determines operating mode:

   * **ONLINE MODE:** Wi-Fi connected AND internet reachable (verified by testing Africa's Talking endpoint)
   * **LOCAL-ONLY MODE:** Wi-Fi absent OR internet unreachable
   * LCD displays mode and Wi-Fi status
5. System behavior:

   * **ONLINE MODE:** Local alerts + SMS notifications enabled
   * **LOCAL-ONLY MODE:** Local alerts only (LCD/LED/Buzzer), SMS alerts disabled but shown as "SMS: OFF" on display

---

### 5.2 Calibration Phase

1. System checks if calibration data exists in memory.
2. If calibration does not exist:

   * LCD displays: "Calibration - Remove weight"
   * Waits for user to press **CAL button (GPIO12)** to tare empty load cell
   * LCD displays: "Place 500g - Press CAL to set"
   * Waits for user to place known calibration weight and press **CAL button** again
   * Computes offset and scale factor
   * Saves calibration data to `calibration.json`
   * LCD confirms: "Calibration OK - Saved"
3. Load calibration values into runtime variables.
4. **During normal monitoring:** Pressing **CAL button** at any time triggers guided re-calibration without interrupting alerts until complete.

---

### 5.3 Monitoring Loop (Continuous Operation)

The system enters a continuous monitoring loop:

1. Read raw weight data from HX711.
2. Apply digital filtering to remove noise and vibration artifacts.
3. Validate sensor data:

   * If invalid, trigger sensor fault alarm and display error on LCD.
4. Convert filtered weight to remaining volume (mL).
5. Compute:

   * Delivered volume
   * Percentage delivered relative to 1500 mL maximum
6. Update LCD with real-time values.
7. Update LEDs based on remaining volume thresholds.
8. Check for low-volume condition (<200 mL):

   * Activate red LED and buzzer
   * Send low-volume SMS if not already sent
9. Check milestone thresholds:

   * Send SMS at 0%, 25%, 50%, and 100% delivered
   * Each milestone SMS is sent once using internal flags

---

### 5.4 Completion and Termination Logic

1. When 100% delivery is reached:

   * LCD displays “IV COMPLETE”
   * Completion buzzer pattern is activated
2. System waits for nurse action:

   * **Acknowledge button (GPIO8):**

     * Silence active alarms without stopping monitoring
   * **New IV button (GPIO9):**

     * Reset volume counters and alert flags
     * Tare load cell
     * Return to monitoring state
   * **Calibrate button (GPIO12):**

     * Trigger guided calibration process
     * Pause monitoring temporarily
     * Replace calibration after completion
   * **Power/Terminate button (GPIO10):**

     * Stop monitoring loop
     * Turn off LEDs and buzzer
     * Display “SESSION ENDED”
     * Program terminates safely

---

## 6. Network Connectivity & SMS Notification System

### 6.1 Online vs Local-Only Modes

The system automatically detects network availability and operates in one of two modes:

**ONLINE MODE (Wi-Fi + Internet OK)**

* Local alerts fully operational (LCD, LED, Buzzer, buttons)
* SMS notifications sent at all milestones (0%, 25%, 50%, 100%, low-volume)
* LCD displays: `Mode: ONLINE`

**LOCAL-ONLY MODE (Wi-Fi missing or Internet unreachable)**

* Local alerts fully operational (LCD, LED, Buzzer, buttons)
* SMS alerts disabled (no network access)
* LCD clearly indicates: `Mode: LOCAL ONLY` or `SMS: OFF`
* System continues monitoring normally without internet dependency
* If internet returns, mode automatically switches to ONLINE

### 6.2 Internet Reachability Check

System does NOT rely on Wi-Fi connection alone. It performs an active test:

1. Check W-Fi association (`WLAN.isconnected()`)
2. Test Africa's Talking API endpoint with a lightweight HTTP request
3. Only if both succeed → ONLINE MODE
4. Mode is checked every 60 seconds during monitoring; automatic recovery when internet returns

### 6.3 SMS Notification System (ONLINE MODE ONLY)

The system integrates with **Africa's Talking SMS API**.

### SMS Behavior (when ONLINE):

* SMS messages are sent when:

  * IV monitoring starts (0% delivered)
  * 25% delivered
  * 50% delivered
  * 100% delivered (completion)
  * Low volume threshold reached (<200 mL)
* SMS sending is protected by flags to prevent duplicate messages.
* The SMS logic is triggered only when MODE = ONLINE.

### 6.4 Local-Only Mode Indicators (LCD Display)

When operating in LOCAL-ONLY mode, the system displays clear indicators:

* Line 1: `WiFi: OFF  SMS: OFF` or `WiFi: OK  SMS: OFF` (depending on Wi-Fi status)
* Line 4: Status includes `LOCAL` or `LOW SMS:OFF` (when low-volume alarm triggers)

This ensures the nurse understands that alarms are active but remote SMS was not sent.

---

## 7. Human Interaction and Safety Considerations

* Alarms can be acknowledged without stopping monitoring.
* System does not automatically restart after IV completion.
* Nurse confirmation is required for new IV or termination.
* Clear START and END states prevent unintended operation.

---

## 8. Expected Outcome

The completed system provides:

* Reliable real-time IV monitoring
* Reduced nurse workload
* Improved patient safety
* Clear visual, audible, and remote notifications
* A scalable foundation for future hospital IoT expansion

