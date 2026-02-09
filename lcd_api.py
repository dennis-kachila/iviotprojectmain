import utime


class LcdApi:
    def __init__(self, num_lines, num_columns):
        self.num_lines = num_lines
        self.num_columns = num_columns
        self.cursor_x = 0
        self.cursor_y = 0

    def clear(self):
        raise NotImplementedError

    def move_to(self, cursor_x, cursor_y):
        self.cursor_x = cursor_x
        self.cursor_y = cursor_y

    def putchar(self, char):
        raise NotImplementedError

    def putstr(self, string):
        for char in string:
            if char == "\n":
                self.cursor_x = 0
                self.cursor_y = min(self.cursor_y + 1, self.num_lines - 1)
                self.move_to(self.cursor_x, self.cursor_y)
            else:
                self.putchar(char)
                self.cursor_x += 1
                if self.cursor_x >= self.num_columns:
                    self.cursor_x = 0
                    self.cursor_y = (self.cursor_y + 1) % self.num_lines
                    self.move_to(self.cursor_x, self.cursor_y)

    def putstr_at(self, string, line):
        self.move_to(0, line)
        # Manual padding since MicroPython doesn't have ljust()
        padded = string + " " * (self.num_columns - len(string)) if len(string) < self.num_columns else string
        self.putstr(padded[:self.num_columns])

    def show_splash(self, lines, delay_ms=1200):
        self.clear()
        for i, line in enumerate(lines[: self.num_lines]):
            self.putstr_at(line, i)
        utime.sleep_ms(delay_ms)
