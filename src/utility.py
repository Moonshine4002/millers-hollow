from .header import *


class NamedEnum(Enum):
    def __str__(self) -> str:
        return f'{self.name.lower()}'


def log(text: str, clear: bool = False, end: str = '\n') -> None:
    if clear:
        with open('log.txt', 'w', encoding='utf-8') as file:
            pass

    with open('log.txt', 'a', encoding='utf-8') as file:
        file.write(text)
        file.write(end)
