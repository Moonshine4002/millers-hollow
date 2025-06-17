import asyncio
from collections import Counter, UserList
from collections.abc import Callable, Generator, Iterable
from copy import copy, deepcopy
from dataclasses import dataclass
from enum import Enum, auto
import itertools
import pathlib
import random
import string
import time
from typing import Any, Literal, NamedTuple, Protocol, Self, TypeAlias
from typing import runtime_checkable


class NamedEnum(Enum):
    def __str__(self) -> str:
        return f'{self.name.lower()}'


@dataclass
class Char:
    name: str
    control: str = 'console'
    model: str = 'human'
    description: str = ''


class Role:
    __match_args__ = ('faction', 'category', 'kind')

    def __init__(
        self,
        faction: str = 'villager',
        category: str = 'villager',
        kind: str = 'villager',
    ) -> None:
        self.faction = faction
        self.category = category
        self.kind = kind

    def __str__(self) -> str:
        return f'{self.faction} - {self.category} - {self.kind}'

    def __bool__(self) -> bool:
        return bool(self.faction)

    def eq_faction(self, value: Self) -> bool:
        return self.faction == value.faction

    def eq_category(self, value: Self) -> bool:
        return self.eq_faction(value) and self.category == value.category

    def eq_kind(self, value: Self) -> bool:
        return self.eq_category(value) and self.kind == value.kind

    def __eq__(self, value: Any) -> bool:
        if isinstance(value, self.__class__):
            return self.eq_kind(value)
        return NotImplemented


class Seat(int):
    def __str__(self) -> str:
        return str(self + 1)

    def __new__(cls, value: int | str) -> Self:
        if isinstance(value, str):
            value = int(value) - 1
        return super().__new__(cls, value)


class LSeat(UserList[Seat]):
    def __init__(self, value: Iterable[Seat | int | str] = []):
        initlist: list[Seat | int | str] = []
        for elem in value:
            if isinstance(elem, str):
                initlist.extend(elem.split('/'))
            else:
                initlist.append(elem)
        super().__init__(map(Seat, initlist))

    def __str__(self) -> str:
        if not self:
            return 'moderator'
        return '/'.join(str(seat) for seat in self)


class LStr(UserList[str]):
    def __init__(self, value: Iterable[LSeat | Seat | int | str] = []):
        initlist: list[Seat | int | str] = []
        for elem in value:
            if isinstance(elem, LSeat):
                initlist.extend(elem)
            elif isinstance(elem, str):
                initlist.extend(elem.split('/'))
            else:
                initlist.append(elem)
        super().__init__(map(str, initlist))

    def __str__(self) -> str:
        if not self:
            return 'moderator'
        return '/'.join(str(elem) for elem in self)


class Phase(NamedEnum):
    DAY = auto()
    NIGHT = auto()

    FIRST = DAY
    LAST = NIGHT

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
    cycle: int = 1
    phase: Phase = Phase.DAY
    stage: int = 0
    # round: int = 0
    tick: int = 0

    def __str__(self) -> str:
        return f'{self.phase} {self.cycle} - {self.stage}'

    def eq_cycle(self, other: Self) -> bool:
        return self.cycle == other.cycle

    def eq_phase(self, other: Self) -> bool:
        return self.eq_cycle(other) and self.phase == other.phase

    def eq_stage(self, other: Self) -> bool:
        return self.eq_phase(other) and self.stage == other.stage

    # def eq_round(self, other: Self) -> bool:
    #    return self.eq_stage(other) and self.round == other.round

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.tick == other.tick
        return NotImplemented

    def inc_phase(self) -> None:
        self.phase = next(self.phase)
        if self.phase == Phase.FIRST:
            self.cycle += 1
        self.stage = 0
        # self.round = 0
        self.tick += 1

    def inc_stage(self) -> None:
        self.stage += 1
        # self.round = 0
        self.tick += 1

    # def inc_round(self) -> None:
    #    self.round += 1
    #    self.tick += 1


class Info(NamedTuple):
    time: Time = Time()
    source: 'tuple[PPlayer, ...]' = ()
    target: 'tuple[PPlayer, ...]' = ()
    content: str = ''

    def __str__(self) -> str:
        return f'[{self.time}]{pls2str(self.source)}> {self.content}'

    def log(self, time: Time) -> str:
        if self.time.eq_stage(time):
            return f'\t{pls2str(self.source)}> {self.content}'
        return str(self)


class Input(NamedTuple):
    prompt: str
    options: tuple[str, ...] = ()

    def __str__(self) -> str:
        options = (
            f' replaced by one of {LStr(self.options)}' if self.options else ''
        )
        return f'["{self.prompt}"{options}]'


class Output(NamedTuple):
    output: str


@runtime_checkable
class PPlayer(Protocol):
    game: 'PGame'
    char: Char
    role: Role
    life: bool
    seat: Seat
    night_priority: int
    vote: float
    can_expose: bool
    death: list[Info]
    tasks: list[Input]
    results: list[Output]

    def __init__(self, game: 'PGame', char: Char, seat: Seat) -> None:
        ...

    def __str__(self) -> str:
        ...

    def str_public(self) -> str:
        ...

    def boardcast(self, pls: Iterable['PPlayer'], content: str) -> None:
        ...

    def day(self) -> None:
        ...

    def night(self) -> None:
        ...

    def expose(self) -> None:
        ...


class Mark(NamedTuple):
    name: str
    game: 'PGame'
    source: PPlayer
    target: PPlayer
    func: Callable[['PGame', PPlayer, PPlayer], None]
    priority: int = 0

    def exec(self) -> None:
        self.func(self.game, self.source, self.target)


class PBadge(Protocol):
    owner: PPlayer | None
    game: 'PGame'

    def __init__(self, game: 'PGame') -> None:
        ...

    def election(self) -> None:
        ...

    def badge(self) -> None:
        ...

    def speakers(self) -> list[PPlayer]:
        ...


class PGame(Protocol):
    chars: list[Char]
    roles: list[type[PPlayer]]
    time: Time
    players: list[PPlayer]
    marks: list[Mark]
    post_marks: list[Mark]
    info: list[Info]
    badge: PBadge

    options: list[PPlayer]
    actors: list[PPlayer]
    died: list[PPlayer]
    data: dict[str, Any]

    def __init__(self) -> None:
        ...

    def __str__(self) -> str:
        ...

    def boardcast(self, pls: Iterable[PPlayer], content: str) -> None:
        ...

    def unicast(self, pl: PPlayer, content: str) -> None:
        ...

    def loop(self) -> None:
        ...

    def day(self) -> None:
        ...

    def night(self) -> None:
        ...

    def exec(self) -> bool:
        ...

    def post_exec(self) -> bool:
        ...

    def winner(self) -> Role:
        ...

    def vote(
        self,
        candidates: Iterable[PPlayer],
        voters: Iterable[PPlayer],
        task: str,
        silent: bool = False,
    ) -> None | PPlayer | list[PPlayer]:
        ...

    def testament(self, died: Iterable[PPlayer]) -> None:
        ...

    def audience(self) -> Generator[PPlayer]:
        ...

    def audience_role(self, role: str) -> Generator[PPlayer]:
        ...

    def alived(self) -> Generator[PPlayer]:
        ...

    def alived_role(self, role: str) -> Generator[PPlayer]:
        ...


def pl2seat(pl: PPlayer) -> Seat:
    return pl.seat


def seat2str(seat: Seat) -> str:
    return str(seat)


def pl2str(pl: PPlayer) -> str:
    return str(pl.seat)


def str2seat(text: str) -> Seat:
    return Seat(text)


def seat2pl(game: PGame, seat: Seat) -> PPlayer:
    return game.players[seat]


def str2pl(game: PGame, text: str) -> PPlayer:
    return game.players[Seat(text)]


def pls2seats(pls: Iterable[PPlayer]) -> Generator[Seat]:
    return (pl.seat for pl in pls)


def seats2str(seats: Iterable[Seat]) -> str:
    return str(LSeat(seats))


def pls2str(pls: Iterable[PPlayer]) -> str:
    return str(LSeat(pl.seat for pl in pls))


def str2seats(texts: str) -> Generator[Seat]:
    return (seat for seat in LSeat(texts))


def seats2pls(game: PGame, seats: Iterable[Seat]) -> Generator[PPlayer]:
    return (game.players[seat] for seat in seats)


def str2pls(game: PGame, texts: str) -> Generator[PPlayer]:
    return (game.players[seat] for seat in LSeat(texts))


class BaseGameError(Exception):
    ...


class SelfExposureError(BaseGameError):
    ...


from . import user_data
