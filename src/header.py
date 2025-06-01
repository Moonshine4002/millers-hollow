from abc import abstractmethod
from collections import UserDict, UserList
from collections.abc import Callable, Sequence
from copy import copy, deepcopy
from dataclasses import dataclass, field
from enum import Enum, auto
import functools
import itertools
import random
import string
import time
from typing import Any, Literal, NamedTuple, Protocol, Self, TypeAlias
import warnings

DEBUG = True


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


@dataclass
class InfoCharacter:
    name: str
    control: str = 'input'


Seat: TypeAlias = int


class Faction:
    __match_args__ = ('faction', 'category')

    def __init__(
        self, faction: str = 'villager', category: str = 'standard'
    ) -> None:
        self.faction = faction
        self.category = category

    def __str__(self) -> str:
        return self.faction + (
            '-' + self.category if self.category != 'standard' else ''
        )

    def __bool__(self) -> bool:
        return bool(self.faction)

    def eq_faction(self, value: Self) -> bool:
        return self.faction == value.faction

    def eq_category(self, value: Self) -> bool:
        return self.category == value.category

    def __eq__(self, value: Any) -> bool:
        if isinstance(value, self.__class__):
            return self.eq_faction(value) and self.eq_category(value)
        return NotImplemented


Role: TypeAlias = str


@dataclass
class InfoRole:
    seat: Seat
    faction: Faction = field(default_factory=Faction)
    role: Role = 'blank'


class Phase(NamedEnum):
    NIGHT = auto()
    DAY = auto()

    FIRST = NIGHT
    LAST = DAY

    def __next__(self) -> Self:
        match self:
            case self.DAY:
                return self.NIGHT
            case self.NIGHT:
                return self.DAY
            case _:
                raise NotImplementedError('unknown phase')


@dataclass
class Time:
    cycle: int = 0
    phase: Phase = Phase.LAST
    round: int = 0

    def __str__(self) -> str:
        return f'cycle {self.cycle} - {self.phase} - round {self.round}'

    def inc_phase(self) -> None:
        self.round = 0
        self.phase = next(self.phase)
        if self.phase == Phase.FIRST:
            self.cycle += 1

    def inc_round(self) -> None:
        self.round += 1


class Mark(NamedTuple):
    name: str
    source: Seat
    target: Seat
    func: Callable[[Seat, Seat], None]
    priority: int = 0

    def exec(self) -> None:
        self.func(self.source, self.target)


class Clue(NamedTuple):
    time: Time
    source: str
    clue: str

    def __str__(self) -> str:
        return f'[{self.time}]{self.source}> {self.clue}'


class PPlayer(Protocol):
    life: bool
    character: InfoCharacter
    role: InfoRole
    clues: list[Clue]
    death_causes: list[str]

    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        ...

    def mark(self, target: Seat) -> Mark:
        ...

    def choose(self, candidates: Sequence[Seat]) -> Seat:
        ...

    def boardcast(self, audiences: Sequence[Seat], content: str) -> None:
        ...

    def text_clues(self) -> str:
        ...


class PGame(Protocol):
    time: Time
    players: list[PPlayer]
    marks: list[Mark]
    post_marks: list[Mark]
