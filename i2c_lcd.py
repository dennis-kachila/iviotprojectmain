from lcd_api import LcdApi
import utime


class I2cLcd(LcdApi):
    def __init__(self, i2c, i2c_addr, num_lines, num_columns):
        self.i2c = i2c
        self.i2c_addr = i2c_addr
        self.backlight = 0x08
        self.ENABLE = 0x04
        self.RS = 0x01

        self._init_lcd()
        super().__init__(num_lines, num_columns)

    def _write_byte(self, data):
        self.i2c.writeto(self.i2c_addr, bytes([data | self.backlight]))

    def _pulse(self, data):
        self._write_byte(data | self.ENABLE)
        utime.sleep_us(1)
        self._write_byte(data & ~self.ENABLE)
        utime.sleep_us(50)

    def _write4bits(self, data):
        self._write_byte(data)
        self._pulse(data)

    def _send(self, value, mode=0):
        high = (value & 0xF0) | mode
        low = ((value << 4) & 0xF0) | mode
        self._write4bits(high)
        self._write4bits(low)

    def _command(self, cmd):
        self._send(cmd, 0)

    def _write_char(self, char):
        self._send(ord(char), self.RS)

    def _init_lcd(self):
        utime.sleep_ms(50)
        self._write4bits(0x30)
        utime.sleep_ms(5)
        self._write4bits(0x30)
        utime.sleep_us(150)
        self._write4bits(0x30)
        self._write4bits(0x20)

        self._command(0x28)
        self._command(0x08)
        self._command(0x01)
        utime.sleep_ms(2)
        self._command(0x06)
        self._command(0x0C)

    def clear(self):
        self._command(0x01)
        utime.sleep_ms(2)

    def move_to(self, cursor_x, cursor_y):
        row_offsets = (0x00, 0x40, 0x14, 0x54)
        addr = cursor_x + row_offsets[cursor_y]
        self._command(0x80 | addr)
        self.cursor_x = cursor_x
        self.cursor_y = cursor_y

    def putchar(self, char):
        self._write_char(char)
