from enum import Enum, auto


class NamedEnum(Enum):
    def __str__(self) -> str:
        return f'{self.name.lower()}'
