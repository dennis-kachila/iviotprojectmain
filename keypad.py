"""
4x3 Membrane Keypad Module for MicroPython
Handles matrix keypad scanning and input buffering
"""

from machine import Pin
import utime

class Keypad:
    """
    4x3 Membrane Keypad Handler
    
    Layout:
    1 2 3
    4 5 6
    7 8 9
    * 0 #
    
    Where:
    # = confirm/enter/next
    * = backspace/use default
    """
    
    # Key mapping for 4x3 matrix
    KEYS = [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['*', '0', '#']
    ]
    
    def __init__(self, row_pins, col_pins, debounce_ms=50):
        """
        Initialize keypad
        
        Args:
            row_pins: List of 4 GPIO pin numbers for rows (outputs)
            col_pins: List of 3 GPIO pin numbers for columns (inputs)
            debounce_ms: Debounce time in milliseconds
        """
        self.debounce_ms = debounce_ms
        self.last_key_time = 0
        self.last_key = None
        
        # Initialize row pins as outputs (high by default)
        self.rows = [Pin(pin, Pin.OUT) for pin in row_pins]
        for row in self.rows:
            row.value(1)
        
        # Initialize column pins as inputs with pull-down resistors
        self.cols = [Pin(pin, Pin.IN, Pin.PULL_DOWN) for pin in col_pins]
    
    def scan(self):
        """
        Scan the keypad matrix and return pressed key
        
        Returns:
            str: Key character if pressed and debounced, None otherwise
        """
        now = utime.ticks_ms()
        
        # Scan each row
        for row_idx, row_pin in enumerate(self.rows):
            # Set current row low, others high
            for r in self.rows:
                r.value(1)
            row_pin.value(0)
            
            # Small delay for signal to settle
            utime.sleep_us(10)
            
            # Check each column
            for col_idx, col_pin in enumerate(self.cols):
                # Column will be low if button in this row is pressed
                # (because row is low and it's pulled down)
                if col_pin.value() == 0:
                    key = self.KEYS[row_idx][col_idx]
                    
                    # Debounce: same key within debounce window
                    if key == self.last_key and utime.ticks_diff(now, self.last_key_time) < self.debounce_ms:
                        return None
                    
                    # New valid key press
                    self.last_key = key
                    self.last_key_time = now
                    
                    # Restore all rows high before returning
                    for r in self.rows:
                        r.value(1)
                    
                    return key
        
        # No key pressed - reset last key after debounce period
        if utime.ticks_diff(now, self.last_key_time) > self.debounce_ms:
            self.last_key = None
        
        # Restore all rows high
        for r in self.rows:
            r.value(1)
        
        return None
    
    def get_key(self):
        """
        Non-blocking key read
        
        Returns:
            str: Key character or None
        """
        return self.scan()


class KeypadInput:
    """
    Helper class for buffered numeric input with keypad
    Handles input validation and display formatting
    """
    
    def __init__(self, keypad, max_digits=4):
        """
        Initialize keypad input buffer
        
        Args:
            keypad: Keypad instance
            max_digits: Maximum number of digits to accept
        """
        self.keypad = keypad
        self.max_digits = max_digits
        self.buffer = ""
        self.last_key_processed = None
    
    def clear(self):
        """Clear input buffer"""
        self.buffer = ""
    
    def get_input(self):
        """
        Get current input buffer as string
        
        Returns:
            str: Current buffer content
        """
        return self.buffer
    
    def process_key(self):
        """
        Process a single keypad scan
        
        Returns:
            tuple: (status, value)
                status: 'digit' | 'confirm' | 'backspace' | 'default' | None
                value: key character or current buffer
        """
        key = self.keypad.get_key()
        
        # Ignore if no key or same key as last processed
        if key is None or key == self.last_key_processed:
            return (None, self.buffer)
        
        self.last_key_processed = key
        
        # Handle special keys
        if key == '#':
            return ('confirm', self.buffer)
        
        elif key == '*':
            # Backspace if buffer has content, otherwise signal default
            if len(self.buffer) > 0:
                self.buffer = self.buffer[:-1]
                return ('backspace', self.buffer)
            else:
                return ('default', self.buffer)
        
        # Handle numeric keys
        elif key.isdigit():
            if len(self.buffer) < self.max_digits:
                self.buffer += key
                return ('digit', self.buffer)
        
        return (None, self.buffer)
    
    def reset_last_key(self):
        """Reset last key tracker to allow key repeat"""
        self.last_key_processed = None
    
    def get_value(self, default=None):
        """
        Get buffer as integer with optional default
        
        Args:
            default: Default value if buffer empty or invalid
            
        Returns:
            int or None: Parsed integer value
        """
        if len(self.buffer) == 0:
            return default
        
        try:
            return int(self.buffer)
        except ValueError:
            return default
