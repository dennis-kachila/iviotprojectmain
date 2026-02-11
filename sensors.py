"""
IV Sensor Module for MicroPython
Handles Drop IR sensor and Bubble detection (IR + Slot module)
"""

from machine import Pin
import utime

class DropSensor:
    """
    Drop IR Sensor Handler
    
    Counts drops using edge detection with debouncing
    Maintains sliding window for rate calculation
    """
    
    def __init__(self, pin, debounce_ms=80):
        """
        Initialize drop sensor
        
        Args:
            pin: GPIO pin number for drop sensor output
            debounce_ms: Minimum time between valid drops (milliseconds)
        """
        self.pin = Pin(pin, Pin.IN)
        self.debounce_ms = debounce_ms
        
        # Counters and timing
        self.total_drops = 0
        self.last_drop_time = utime.ticks_ms()
        self.last_state = self.pin.value()
        
        # Sliding window for rate calculation (timestamps of last 60s)
        self.drop_timestamps = []
    
    def update(self):
        """
        Update sensor state and detect drops
        
        Returns:
            bool: True if new drop detected, False otherwise
        """
        now = utime.ticks_ms()
        current_state = self.pin.value()
        
        # Detect rising edge (low to high transition)
        if current_state == 1 and self.last_state == 0:
            # Check debounce
            time_since_last = utime.ticks_diff(now, self.last_drop_time)
            
            if time_since_last >= self.debounce_ms:
                # Valid drop detected
                self.total_drops += 1
                self.last_drop_time = now
                self.drop_timestamps.append(now)
                
                # Clean old timestamps (older than 60 seconds)
                self._clean_old_timestamps(now)
                
                self.last_state = current_state
                return True
        
        self.last_state = current_state
        
        # Clean old timestamps periodically even without drops
        self._clean_old_timestamps(now)
        
        return False
    
    def _clean_old_timestamps(self, now):
        """Remove timestamps older than 60 seconds"""
        cutoff = now - 60000  # 60 seconds in milliseconds
        self.drop_timestamps = [ts for ts in self.drop_timestamps if utime.ticks_diff(now, ts) <= 60000]
    
    def get_total_drops(self):
        """Get total drop count"""
        return self.total_drops
    
    def get_drops_per_minute(self):
        """
        Calculate drops per minute from last 60 seconds
        
        Returns:
            float: Drops per minute (gtt/min)
        """
        return len(self.drop_timestamps)
    
    def get_time_since_last_drop(self):
        """
        Get time elapsed since last drop
        
        Returns:
            int: Milliseconds since last drop
        """
        return utime.ticks_diff(utime.ticks_ms(), self.last_drop_time)
    
    def reset(self):
        """Reset drop counter and timestamps"""
        self.total_drops = 0
        self.last_drop_time = utime.ticks_ms()
        self.drop_timestamps = []


class BubbleDetector:
    """
    Dual-Sensor Bubble Detection
    
    Requires BOTH Bubble IR and Bubble Slot sensors to confirm
    within a specified time window
    """
    
    def __init__(self, bubble_ir_pin, bubble_slot_pin, confirm_window_ms=400):
        """
        Initialize bubble detector
        
        Args:
            bubble_ir_pin: GPIO pin for Bubble IR sensor output
            bubble_slot_pin: GPIO pin for Bubble Slot module DO output
            confirm_window_ms: Time window for dual confirmation (milliseconds)
        """
        self.bubble_ir = Pin(bubble_ir_pin, Pin.IN)
        self.bubble_slot = Pin(bubble_slot_pin, Pin.IN)
        self.confirm_window_ms = confirm_window_ms
        
        # State tracking
        self.last_ir_state = self.bubble_ir.value()
        self.last_slot_state = self.bubble_slot.value()
        
        # Event timestamps
        self.last_ir_trigger = None
        self.last_slot_trigger = None
        
        # Bubble status
        self.bubble_detected = False
        self.bubble_confirmed = False
    
    def update(self):
        """
        Update bubble detector state
        
        Returns:
            bool: True if bubble newly confirmed, False otherwise
        """
        now = utime.ticks_ms()
        
        # Read current states
        ir_state = self.bubble_ir.value()
        slot_state = self.bubble_slot.value()
        
        # Detect IR sensor trigger (change to active state)
        # Assuming active low (sensor outputs low when bubble detected)
        if ir_state == 0 and self.last_ir_state == 1:
            self.last_ir_trigger = now
        
        # Detect Slot sensor trigger
        if slot_state == 0 and self.last_slot_state == 1:
            self.last_slot_trigger = now
        
        # Update last states
        self.last_ir_state = ir_state
        self.last_slot_state = slot_state
        
        # Check for bubble confirmation
        # Both sensors must have triggered within the confirmation window
        if self.last_ir_trigger is not None and self.last_slot_trigger is not None:
            time_diff = abs(utime.ticks_diff(self.last_ir_trigger, self.last_slot_trigger))
            
            if time_diff <= self.confirm_window_ms:
                # Bubble confirmed by both sensors
                if not self.bubble_confirmed:
                    self.bubble_detected = True
                    self.bubble_confirmed = True
                    return True
        
        # Clear old triggers if they haven't confirmed within window
        if self.last_ir_trigger is not None:
            if utime.ticks_diff(now, self.last_ir_trigger) > self.confirm_window_ms:
                if not self.bubble_confirmed:
                    self.last_ir_trigger = None
        
        if self.last_slot_trigger is not None:
            if utime.ticks_diff(now, self.last_slot_trigger) > self.confirm_window_ms:
                if not self.bubble_confirmed:
                    self.last_slot_trigger = None
        
        return False
    
    def is_bubble_detected(self):
        """
        Check if bubble is currently detected
        
        Returns:
            bool: True if bubble confirmed
        """
        return self.bubble_confirmed
    
    def clear_bubble(self):
        """Clear bubble detection state (after acknowledgment)"""
        self.bubble_detected = False
        self.bubble_confirmed = False
        self.last_ir_trigger = None
        self.last_slot_trigger = None
    
    def reset(self):
        """Full reset of bubble detector"""
        self.clear_bubble()
        self.last_ir_state = self.bubble_ir.value()
        self.last_slot_state = self.bubble_slot.value()
