from machine import Pin
import utime


class HX711:
    def __init__(self, dout_pin, pd_sck_pin, gain=128):
        self.dout = Pin(dout_pin, Pin.IN, pull=Pin.PULL_UP)
        self.pd_sck = Pin(pd_sck_pin, Pin.OUT)
        self.pd_sck.value(0)
        self.set_gain(gain)

    def set_gain(self, gain):
        if gain not in (128, 64, 32):
            raise ValueError("gain must be 128, 64, or 32")
        self.gain = gain
        self._gain_pulses = {128: 1, 64: 3, 32: 2}[gain]

    def is_ready(self):
        return self.dout.value() == 0

    def read_raw(self, timeout_ms=1000):
        start = utime.ticks_ms()
        while not self.is_ready():
            if utime.ticks_diff(utime.ticks_ms(), start) > timeout_ms:
                return None
            utime.sleep_ms(1)

        data = 0
        for _ in range(24):
            self.pd_sck.value(1)
            utime.sleep_us(1)
            data = (data << 1) | self.dout.value()
            self.pd_sck.value(0)
            utime.sleep_us(1)

        for _ in range(self._gain_pulses):
            self.pd_sck.value(1)
            utime.sleep_us(1)
            self.pd_sck.value(0)
            utime.sleep_us(1)

        if data & 0x800000:
            data |= ~0xFFFFFF

        return data

    def read_average(self, times=5):
        total = 0
        for _ in range(times):
            value = self.read_raw()
            if value is None:
                return None
            total += value
        return total // times
