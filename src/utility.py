from .header import *


class ModifiedEnum(Enum):
    def __str__(self) -> str:
        return f'{self.name.lower()}'
