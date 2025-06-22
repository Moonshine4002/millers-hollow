import asyncio
from collections import Counter, UserList, UserString
from collections.abc import Callable, Generator, Iterable
from copy import copy, deepcopy
from dataclasses import dataclass
import datetime
from enum import Enum, auto
import functools
import itertools
import pathlib
import random
import string
import time
from typing import Any, Literal, NamedTuple, Protocol, Self, TypeAlias
from typing import final, runtime_checkable


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


class State(NamedEnum):
    BEGIN = auto()
    DAY = auto()
    NIGHT = auto()
    END = auto()

    FIRST = DAY
    LAST = NIGHT


class Time:
    def __init__(self) -> None:
        self.start = datetime.datetime.now()
        self.datetime = datetime.datetime.now()
        self.state = State.BEGIN
        self.step = 0

    def __str__(self) -> str:
        return self.datetime.strftime('%d-%H:%M:%S')

    def time_inc(self) -> None:
        self.time_add(datetime.timedelta(hours=1))

    def time_add(self, delta: datetime.timedelta) -> None:
        self.datetime += delta
        self.refresh()

    def time_set(self, time: datetime.time) -> None:
        self.datetime = datetime.datetime.combine(self.datetime, time)
        self.refresh()

    def eq_date(self, other: Self) -> bool:
        return self.datetime.date() == other.datetime.date()

    def eq_state(self, other: Self) -> bool:
        return self.eq_date(other) and self.state == other.state

    def eq_step(self, other: Self) -> bool:
        return self.step == other.step

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.eq_step(other)
        return NotImplemented

    def refresh(self) -> None:
        self.step += 1
        if 6 <= self.datetime.hour < 18:
            self.state = State.DAY
        else:
            self.state = State.NIGHT


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


class Info(NamedTuple):
    game: 'PGame'
    time: Time = Time()
    source: tuple['PPlayer', ...] = ()
    target: tuple['PPlayer', ...] = ()
    content: str = ''

    def __str__(self) -> str:
        return f'[{self.time}]{pls2str(self.source)}> {self.content}'


class Mark(NamedTuple):
    name: str
    info: Info
    priority: int = 0

    def exec(self) -> None:
        for t in self.info.target:
            if skill := t.skills.get(self.name):
                skill(self)
                continue
            for s in self.info.source:
                if skill := s.skills.get(self.name):
                    skill(self)
                    break
            else:
                raise RuntimeError('no skill')


Skill: TypeAlias = Callable[[Mark], None]


class Marks(UserList[Mark]):
    def __init__(self, pl: 'PPlayer') -> None:
        self.pl = pl
        super().__init__()

    def reset(self, marks: Iterable[Mark]) -> None:
        self.data = list(marks)

    def add(
        self, name: str, source: Iterable['PPlayer'], priority: int = 0
    ) -> None:
        game = self.pl.game
        info = Info(game, copy(game.time), tuple(source), (self.pl,))
        return super().append(Mark(name, info, priority))

    def add_exec(self, name: str, source: Iterable['PPlayer']) -> None:
        game = self.pl.game
        info = Info(game, copy(game.time), tuple(source), (self.pl,))
        Mark(name, info).exec()

    def exec(self) -> None:
        while self:
            self.sort(key=lambda mark: mark.priority)
            mark = self.pop()
            mark.exec()


@runtime_checkable
class PPlayer(Protocol):
    game: 'PGame'
    char: Char
    seat: Seat
    life: bool
    role: Role
    skills: dict[str, Skill]
    marks: Marks
    death: Marks
    tasks: list[Input]
    results: list[Output]

    vote: float
    can_expose: bool = False

    def __init__(self, game: 'PGame', char: Char, seat: Seat) -> None:
        ...

    def __str__(self) -> str:
        ...

    def str_public(self) -> str:
        ...

    @staticmethod
    def cast(info: Info) -> None:
        ...

    def boardcast(self, pls: Iterable['PPlayer'], content: str) -> None:
        ...

    def receive(self, content: str) -> None:
        ...

    def loop(self) -> None:
        ...

    def day(self) -> None:
        ...

    def night(self) -> None:
        ...

    def dying(self) -> None:
        ...

    def verdict(self) -> None:
        ...

    def exec(self) -> None:
        ...

    def killed(self, mark: Mark) -> None:
        ...

    def expose(self) -> None:
        ...


class PBadge(Protocol):
    game: 'PGame'
    owner: PPlayer | None

    def __init__(self, game: 'PGame') -> None:
        ...

    def election(self) -> None:
        ...

    def transfer(self) -> None:
        ...

    def speakers(self) -> list[PPlayer]:
        ...


class PGame(Protocol):
    chars: list[Char]
    roles: list[type[PPlayer]]
    time: Time
    players: list[PPlayer]
    info: list[Info]
    badge: PBadge

    winner: Role
    options: list[PPlayer]
    died: list[PPlayer]

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

    def verdict(self) -> None:
        ...

    def exec(self) -> None:
        ...

    def testament(self) -> None:
        ...

    def vote(
        self,
        candidates: Iterable[PPlayer],
        voters: Iterable[PPlayer],
        task: str,
        silent: bool = False,
    ) -> list[PPlayer]:
        ...

    def audience(self) -> Generator[PPlayer]:
        ...

    def alived(self) -> Generator[PPlayer]:
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


class TimeChangedError(BaseGameError):
    ...


from . import user_data
