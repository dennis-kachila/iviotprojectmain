"""
Custom logging module for MicroPython on Raspberry Pi Pico
Writes logs to file with timestamp, log level, and message
Default file: system.log (for real hardware Pico deployment)
"""

import utime
import os


class Logger:
    """Simple file-based logging for MicroPython"""
    
    # Log levels
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    
    LEVEL_NAMES = {
        10: "DEBUG",
        20: "INFO",
        30: "WARNING",
        40: "ERROR",
        50: "CRITICAL",
    }
    
    def __init__(self, log_file="system.log", max_file_size=50000, level=INFO):
        """
        Initialize logger
        
        Args:
            log_file: Path to log file (default: system.log for Pico hardware)
            max_file_size: Max file size before rotation (bytes)
            level: Minimum log level to write (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.log_file = log_file
        self.max_file_size = max_file_size
        self.level = level
        self._ensure_log_file_exists()
    
    def _ensure_log_file_exists(self):
        """Create log file if it doesn't exist"""
        try:
            with open(self.log_file, "a") as f:
                pass  # Just create if missing
        except OSError:
            pass
    
    def _rotate_log(self):
        """Rotate log file if it exceeds max size"""
        try:
            file_stat = os.stat(self.log_file)
            if file_stat[6] > self.max_file_size:
                # Rename current log to backup
                try:
                    os.remove(self.log_file + ".bak")
                except OSError:
                    pass
                try:
                    os.rename(self.log_file, self.log_file + ".bak")
                except OSError:
                    pass
                # Create new log file
                with open(self.log_file, "w") as f:
                    f.write("=== Log rotated (file was too large) ===\n")
        except OSError:
            pass
    
    def _format_message(self, level, message):
        """Format log message with timestamp and level"""
        # Get current time (Unix epoch as fallback if RTC not set)
        try:
            t = utime.localtime()
            timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                t[0], t[1], t[2], t[3], t[4], t[5]
            )
        except:
            timestamp = "????-??-?? ??:??:??"
        
        level_name = self.LEVEL_NAMES.get(level, "UNKNOWN")
        return "[{}] [{}] {}".format(timestamp, level_name, message)
    
    def _write_log(self, level, message):
        """Write log to file"""
        if level < self.level:
            return
        
        formatted = self._format_message(level, message)
        
        try:
            self._rotate_log()
            with open(self.log_file, "a") as f:
                f.write(formatted + "\n")
        except OSError as e:
            # Fallback: print to console if file write fails
            print("LOG ERROR: " + formatted)
    
    def debug(self, message):
        """Log debug message"""
        self._write_log(self.DEBUG, message)
    
    def info(self, message):
        """Log info message"""
        self._write_log(self.INFO, message)
    
    def warning(self, message):
        """Log warning message"""
        self._write_log(self.WARNING, message)
    
    def error(self, message):
        """Log error message"""
        self._write_log(self.ERROR, message)
    
    def critical(self, message):
        """Log critical message"""
        self._write_log(self.CRITICAL, message)
    
    def set_level(self, level):
        """Set minimum log level"""
        self.level = level
    
    def clear_log(self):
        """Clear log file"""
        try:
            with open(self.log_file, "w") as f:
                f.write("=== Log cleared ===\n")
        except OSError:
            pass
    
    def read_log(self, lines=50):
        """Read last N lines from log file"""
        try:
            with open(self.log_file, "r") as f:
                all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except OSError:
            return []


# Global logger instance
_logger = None


def get_logger(log_file="system.log", level=Logger.INFO):
    """Get or create global logger instance"""
    global _logger
    if _logger is None:
        _logger = Logger(log_file=log_file, level=level)
    return _logger


# Convenience functions
def debug(message):
    get_logger().debug(message)


def info(message):
    get_logger().info(message)


def warning(message):
    get_logger().warning(message)


def error(message):
    get_logger().error(message)


def critical(message):
    get_logger().critical(message)


def set_level(level):
    get_logger().set_level(level)


def clear_log():
    get_logger().clear_log()


def read_log(lines=50):
    return get_logger().read_log(lines)
