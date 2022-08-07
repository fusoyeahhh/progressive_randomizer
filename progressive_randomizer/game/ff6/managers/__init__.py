from dataclasses import dataclass
import logging
log = logging.getLogger()

# FIXME: to base components?
@dataclass
class BoundedQuantity:
    value: int
    max_value: int
    min_value: int = 0

    def set_value(self, val):
        self.value = max(self.min_value, min(self.max_value, val))

    def set_bound(self, lower=None, upper=None):
        self.min_value = lower or self.min_value
        self.max_value = upper or self.max_value

        # reset to bounds if needed
        self.set_value(self.value)

    def __int__(self):
        return self.value

    def __bytes__(self):
        return bytes([self.value])

    def str(self):
        return f"{self.value}"