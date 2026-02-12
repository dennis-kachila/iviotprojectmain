# Comprehensive Project Description and Implementation Guide

## **Modified IoT-Based IV Fluid Monitoring, Prescription-Controlled Drop Counting and Bubble Detection System**

### *(Drop IR + Bubble IR + Bubble Slot Module, Keypad Prescription Input)*

---

## 1. Purpose and System Summary

This system is a **modified IV infusion monitoring and alert device** designed to help nurses monitor and verify IV delivery based on a **prescribed volume and time**, while ensuring safety through **bubble detection** and **no-flow detection**, and optional **SMS notifications** when network is available.

The device:

1. Accepts a **prescription** from a nurse using a **4×3 membrane keypad**:

   * Target Volume to be delivered (mL)
   * Time duration (hours and/or minutes)
   * Optional drip factor (gtt/mL) – default used if not provided
2. Calculates and displays:

   * Required drip rate in **gtt/min**
   * Real-time delivered volume, remaining volume, % delivered
   * Real-time measured drop rate and flow rate (mL/hr)
   * Estimated time remaining (ETA), if flow is measurable
3. Monitors infusion using:

   * **Drop IR sensor** to count drops (single source of truth for drop count)
4. Detects bubbles using:

   * **Bubble IR sensor** AND **Bubble Slot sensor module**
   * Bubble event is valid only if both confirm within a time window
5. Provides alerts:

   * LCD messages, LED status, buzzer patterns
   * SMS alerts via Africa’s Talking in ONLINE mode
6. Supports nurse controls using buttons:

   * Acknowledge (silence buzzer)
   * New IV (reset and re-enter prescription)
   * Calibration (reset counters only, keep prescription)
   * Terminate (end program safely)
7. Works even without internet:

   * Local-only mode keeps monitoring + alarms active
   * SMS disabled when offline

---

## 2. Hardware Components

### 2.1 Controller and UI

* Raspberry Pi Pico W (MicroPython)
* 20×4 I2C LCD (address typically 0x27)
* 3 LEDs: Red, Yellow, Green
* Passive buzzer (PWM)
* Push buttons (4)
* 4×3 membrane keypad (7-wire matrix)

### 2.2 Sensors (Modified Design)

* **Drop IR Sensor** (digital output module): counts drops
* **Bubble IR Sensor** (digital output module): detects bubble changes
* **Bubble Slot Sensor Module** (LM393 speed/tacho optocoupler module): bubble confirmation

---

## 3. Final GPIO Mapping

### 3.1 Existing assignments (fixed)

* GPIO8  : Acknowledge/Reset Button (input, pull-down)

* GPIO9  : New IV Button (input, pull-down)

* GPIO10 : Terminate Button (input, pull-down)

* GPIO12 : Calibration Button (input, pull-down)

* GPIO11 : Buzzer (output, PWM)

* GPIO16 : LCD SDA (I2C0)

* GPIO17 : LCD SCL (I2C0)

* GPIO18 : Red LED (output)

* GPIO19 : Yellow LED (output)

* GPIO20 : Green LED (output)

### 3.2 Sensor inputs (finalized in this modification)

(Choose these GPIOs if free; AI agent can adjust if your board wiring differs.)

* GPIO21 : Drop IR sensor output (input)
* GPIO22 : Bubble IR sensor output (input)
* GPIO26 : Bubble Slot module DO output (input)

> All sensors should be powered from **3.3V** so the Pico inputs are safe.

### 3.3 Keypad mapping (7 pins: 4 rows + 3 columns)

Suggested (adjust if conflicts):

* Rows (outputs): GPIO2, GPIO3, GPIO4, GPIO5
* Columns (inputs with pull-down or pull-up): GPIO6, GPIO7, GPIO13

---

## 4. Core Configuration Values (Must Be Constants)

These are required for predictable behavior and must be defined clearly:

### Prescription defaults

* DEFAULT_DRIP_FACTOR = 20 (gtt/mL)
* DEFAULT_TARGET_VOLUME_ML = none (must be entered)
* DEFAULT_DURATION = none (must be entered)

### Time and detection parameters

* DROP_DEBOUNCE_MS = 80 (ignore pulses occurring faster than this)
* DROP_CONFIRM_TIMEOUT_SEC = 30 (no-drop timeout for possible complete or no-flow)
* BUBBLE_CONFIRM_WINDOW_MS = 400 (bubble sensors must agree within this window)
* NETWORK_RECHECK_SEC = 60 (how often to re-check internet during monitoring)

### Alarm thresholds

* LOW_VOLUME_THRESHOLD_ML = 200
* WARNING_VOLUME_THRESHOLD_ML = 300 (used for LED thresholds)

### Milestone percentages (relative to prescription)

* MILESTONES = [0, 25, 50, 100]

---

## 5. Drip Factor and IV Set Note (Critical)

Drop factor comes from the **IV administration set** (tubing/drip chamber), not the IV bag. The nurse can input it via keypad. If not input, the system uses DEFAULT_DRIP_FACTOR.

Common values:

* 10, 15, 20 gtt/mL (macrodrip)
* 60 gtt/mL (microdrip)

---

## 6. Prescription Input via Keypad (Required User Flow)

### 6.1 Keypad meanings

* Digits 0–9: numeric entry
* `#` : confirm / enter / next field
* `*` : backspace or “use default” depending on prompt

### 6.2 Prescription input sequence (mandatory)

At startup or after “New IV”:

**Step 1: Enter Target Volume**

* LCD: “Enter Volume (mL):”
* Nurse types numbers (e.g., 120)
* `#` confirms
* Validate: 1–1500 mL (or your chosen limit)

**Step 2: Enter Duration**

* LCD: “Enter Time (min):” (recommended to use minutes to avoid confusion)
* Nurse enters duration in minutes (e.g., 240 for 4 hours)
* `#` confirms
* Validate: >0 and reasonable (e.g., 1–1440 minutes)

**Step 3: Enter Drip Factor (Optional)**

* LCD: “Drip Factor gtt/mL (*=20):”
* If nurse presses `*` → use DEFAULT_DRIP_FACTOR
* Or nurse types value (10/15/20/60) then `#`
* Validate: allow only known values or allow any integer range 1–100 with warning

After inputs confirmed, show computed drip rate.

---

## 7. Calculations (Must Be Implemented Exactly)

### 7.1 Prescribed flow rate

Let:

* V_target_ml
* T_minutes
* drip_factor_gtt_ml

Compute:

* mL_per_hr_prescribed = (V_target_ml / T_minutes) * 60
* gtt_per_min_target = (mL_per_hr_prescribed * drip_factor_gtt_ml) / 60
  Simplifies to:
  **gtt_per_min_target = (V_target_ml * drip_factor_gtt_ml) / T_minutes**

Display to nurse:

* “Set drip: XX gtt/min”

### 7.2 Delivered volume from drops

Let:

* total_drops (validated drop pulses)

Compute:

* delivered_ml = total_drops / drip_factor_gtt_ml
* remaining_ml = max(0, V_target_ml - delivered_ml)
* percent_delivered = min(100, (delivered_ml / V_target_ml) * 100)

### 7.3 Measured flow rate from actual drops

Maintain drops in the last 60 seconds:

* gtt_per_min_measured = drops_last_60s
* mL_per_hr_measured = (gtt_per_min_measured * 60) / drip_factor_gtt_ml

ETA estimate (only if measured rate > 0):

* ETA_hours = remaining_ml / mL_per_hr_measured

---

## 8. Drop Sensor Logic (Drop IR Only)

### 8.1 Event detection

Drop IR output generates pulses when drops pass. The system must:

* Detect edges (preferably rising edge)
* Apply debounce using DROP_DEBOUNCE_MS to avoid double counting

### 8.2 Drop counting method

When a valid drop occurs:

* total_drops += 1
* last_drop_time = now
* add timestamp to a sliding window list (for 60s rate)
* update delivered_ml and percent

---

## 9. Bubble Detection Logic (Bubble IR + Bubble Slot Confirmation)

### 9.1 Truth rule (must confirm)

A bubble is valid ONLY if both sensors indicate bubble within window:

ValidBubble = BubbleIR AND BubbleSlot within BUBBLE_CONFIRM_WINDOW_MS

### 9.2 Bubble detection mechanism

Implementation approach:

* When Bubble IR triggers, store time
* When Bubble Slot triggers, store time
* If both triggers exist and abs(timeA - timeB) <= window → ValidBubble True
* If only one triggers and the other does not within the window → ignore (false)

### 9.3 Bubble alarm response (highest priority)

On ValidBubble:

* Red LED ON or fast blink
* Buzzer: continuous tone or rapid alarm
* LCD: “BUBBLE DETECTED”
* In ONLINE mode: send SMS “BUBBLE DETECTED – CHECK LINE”
* Stay in bubble-alarm state until nurse acknowledges (GPIO8)

  * Acknowledge silences buzzer but bubble status remains displayed until bubble clears or nurse restarts

---

## 10. No-Drop Timeout Logic (Completion vs No-Flow/Occlusion)

### 10.1 No-drop timeout condition

If:

* (now - last_drop_time) > DROP_CONFIRM_TIMEOUT_SEC

Then infusion is either:

* Completed, or
* No flow / occlusion / clamp closed

### 10.2 Distinguish complete vs no-flow

Check two conditions:

**Completion Condition**

* delivered_ml >= V_target_ml (or percent_delivered >= 100)

If true:

* State = COMPLETE

**No-flow Condition**

* delivered_ml < V_target_ml and no drops for timeout

If true:

* State = NO_FLOW / OCCLUSION
* Alarm message differs from COMPLETE
* Provide buzzer + LCD warning and optional SMS (ONLINE)

---

## 11. Time Elapsed Alarm (Prescription-Time Completion)

The system must also track time since infusion started.

* StartTime is set when monitoring begins (after prescription confirmed)
* ElapsedTime = now - StartTime

### 11.1 Time-elapsed conditions

If:

* ElapsedTime >= T_minutes * 60 seconds

Then time has elapsed.

**Two outcomes:**

1. If delivered_ml >= V_target_ml:

   * COMPLETE (normal success)
2. If delivered_ml < V_target_ml:

   * TIME ELAPSED BUT UNDERDELIVERED (rate too slow / no flow)
   * Alarm nurse

This is important because sometimes drops continue but too slowly; time-based logic catches that.

---

## 12. Milestone Alerts (0%, 25%, 50%, 100%)

Milestones are relative to prescription volume, not 1500 mL.

Milestone triggers:

* When percent_delivered crosses >= 0, 25, 50, 100
* Each milestone must be sent only once using flags:

  * sent_0, sent_25, sent_50, sent_100

**SMS gating:**

* Only send SMS if MODE = ONLINE

---

## 13. LED Rules (Simple and deterministic)

LEDs indicate remaining volume relative to prescription:

* Green: remaining_ml >= 300
* Yellow: 200 <= remaining_ml < 300
* Red: remaining_ml < 200

Overrides:

* Bubble alarm overrides all → Red
* Sensor fault overrides all → Red fast blink

---

## 14. Buzzer Patterns and Priority

Priority order (highest first):

1. Bubble detected
2. Sensor fault (if implemented)
3. No-flow / occlusion
4. Low volume
5. Time elapsed underdelivered
6. Completion tone

Acknowledge button (GPIO8):

* Silences buzzer for current alarm
* Does NOT stop monitoring unless in terminated state

---

## 15. Operating Modes: ONLINE vs LOCAL-ONLY

### 15.1 Mode determination

* Attempt Wi-Fi connect
* If connected, perform HTTP reachability check (Africa’s Talking endpoint)
* ONLINE only if BOTH succeed

### 15.2 Behavior

* ONLINE: SMS enabled
* LOCAL-ONLY: SMS disabled; LCD shows “SMS OFF”

System must re-check network every NETWORK_RECHECK_SEC while monitoring.

**No catch-up SMS by default:** do not send missed milestone texts after reconnection unless explicitly designed.

---

## 16. Africa’s Talking SMS Integration

In ONLINE mode, send SMS for:

* Milestones: 0, 25, 50, 100
* Low volume threshold
* Bubble detected
* No flow / occlusion
* Time elapsed underdelivered (optional)

SMS function must:

* Be non-blocking or timeout-protected
* Catch exceptions so monitoring never stops if SMS fails

---

## 17. User Buttons: Exact Behaviors

### Acknowledge (GPIO8)

* Silences buzzer immediately
* Leaves alert state visible on LCD
* Monitoring continues

### New IV (GPIO9) — “Reset and Re-enter Prescription”

* Full session reset:

  * clear prescription values
  * reset counters
  * reset milestone flags
  * reset StartTime
* Transition to PRESCRIPTION_INPUT

### Calibration (GPIO12) — “Reset counters only”

* Keeps prescription values (volume, time, drip factor)
* Resets monitoring counters:

  * total_drops = 0
  * delivered_ml = 0
  * milestone flags reset
  * last_drop_time = now
  * StartTime reset to now (recommended)
* Returns to MONITORING state

### Terminate (GPIO10)

* Clean program stop:

  * turn off buzzer
  * turn off LEDs
  * display “SESSION ENDED”
  * set state TERMINATED (stop loop)

---

## 18. LCD Display Requirements (20×4)

The LCD must show enough detail to operate without ambiguity.

Recommended layout during monitoring:

* Line 1: `VOL 075/120 mL`
* Line 2: `% 62  Rem 45mL`
* Line 3: `Rate 28gtt  25mLh`
* Line 4: `ONLINE  SMS ON`

During alarm:

* Bubble: `BUBBLE DETECTED`
* No flow: `NO FLOW CHECK LINE`
* Time elapsed: `TIME DONE UNDER`
* Complete: `INFUSION COMPLETE`

During offline:

* `LOCAL ONLY SMS OFF`

---

## 19. Required State Machine (AI Agent Must Implement)

Define explicit states:

* STATE_INIT
* STATE_MODE_CHECK
* STATE_PRESCRIPTION_INPUT
* STATE_RATE_DISPLAY
* STATE_MONITORING
* STATE_BUBBLE_ALARM
* STATE_LOW_VOLUME (can be a flag within monitoring)
* STATE_NO_FLOW
* STATE_TIME_ELAPSED
* STATE_COMPLETE
* STATE_TERMINATED

Transitions must follow the rules above; alarms can be implemented as state overrides or priority flags.

---

## 20. Implementation Structure for MicroPython (Module Layout Suggestion)

Recommended file structure:

* `main.py`

  * state machine
  * event loop
  * LCD updates
  * buttons handling
  * network mode checking
  * SMS triggers

* `keypad.py`

  * keypad scanning
  * key mapping and input buffer handling

* `sensors.py`

  * drop IR edge detection
  * bubble IR and bubble slot detection
  * debounce and confirmation windows

* `sms.py`

  * Africa’s Talking REST wrapper using `urequests`
  * safe timeouts and exception handling

* `config.py`

  * constants and defaults
  * saved settings if needed (json)

---

## 21. Final Notes (So the AI agent doesn’t miss details)

1. Drops are counted from **only Drop IR** (single source).
2. Bubble is valid only when **Bubble IR AND Bubble Slot** confirm within a time window.
3. Prescription volume (e.g., 120 mL) defines what “100%” means.
4. Completion requires either:

   * delivered volume reached, OR
   * no-drop timeout with delivered volume near/at target, OR
   * time elapsed with delivered volume reached
5. If time elapsed but volume not delivered → alarm nurse.
6. If no drops and volume not delivered → NO FLOW / occlusion alarm.
7. SMS only runs in ONLINE mode; local alerts always run.
8. “New IV” clears everything and forces re-entry of prescription.
9. “Calibration” resets counters only and keeps prescription.
