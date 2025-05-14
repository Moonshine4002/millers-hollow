from .header import *


class ModifiedEnum(Enum):
    def __str__(self):
        return f'{self.name.lower()}'
