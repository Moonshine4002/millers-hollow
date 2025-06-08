from collections import Counter
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


from . import user_data

DEBUG: bool = user_data.DEBUG
# api_key: str = user_data.api_key
# base_url: str = user_data.base_url
# models: list[str] = user_data.models
# win_condition: Literal[
#    'all', 'partial'
# ] = user_data.win_condition   # type: ignore[assignment]
# allow_exposure: bool = user_data.allow_exposure
# election_round: int = user_data.election_round
# user_names: list[str] = user_data.user_names
# language: str = user_data.language
# additional_prompt: str = user_data.additional_prompt


class NamedEnum(Enum):
    def __str__(self) -> str:
        return f'{self.name.lower()}'


@dataclass
class Char:
    name: str
    control: str = 'console'
    model: str = 'human'


class Seat(int):
    def __str__(self) -> str:
        return str(self + 1)

    def __new__(cls, value: int | str) -> Self:
        if isinstance(value, str):
            value = int(value) - 1
        return super().__new__(cls, value)


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
    round: int = 0

    def __str__(self) -> str:
        return f'{self.phase} {self.cycle} - {self.round}'

    def inc_phase(self) -> None:
        self.round = 0
        self.phase = next(self.phase)
        if self.phase == Phase.FIRST:
            self.cycle += 1

    def inc_round(self) -> None:
        self.round += 1


class Clue(NamedTuple):
    time: Time
    source: str
    content: str

    def __str__(self) -> str:
        return f'[{self.time}]{self.source}> {self.content}'


@runtime_checkable
class PPlayer(Protocol):
    game: 'PGame'
    char: Char
    role: Role
    life: bool
    seat: Seat
    vote: float
    night_priority: int
    clues: list[Clue]
    death_time: Time
    death_causes: list[str]

    def __init__(self, game: 'PGame', char: Char, seat: Seat) -> None:
        ...

    def __str__(self) -> str:
        ...

    def boardcast(self, pls: Iterable['PPlayer'], content: str) -> None:
        ...

    def unicast(self, pl: 'PPlayer', content: str) -> None:
        ...

    def receive(self, content: str) -> None:
        ...

    def day(self) -> None:
        ...

    def night(self) -> None:
        ...

    def speech_expose(self) -> str:
        ...

    def speech_withdraw_expose(self) -> tuple[str, str]:
        ...

    def str_mandatory(self, options: Iterable[str]) -> str:
        ...

    def str_optional(self, options: Iterable[str]) -> str:
        ...

    def pl_mandatory(self, options: Iterable['PPlayer']) -> 'PPlayer':
        ...

    def pl_optional(self, options: Iterable['PPlayer']) -> 'PPlayer | None':
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


def pls2seat(pls: Iterable[PPlayer]) -> Generator[Seat]:
    return (pl.seat for pl in pls)


def pls2lstr(pls: Iterable[PPlayer]) -> Generator[str]:
    return (str(seat) for seat in pls2seat(pls))


def pls2str(pls: Iterable[PPlayer]) -> str:
    return f"[{', '.join(pls2lstr(pls))}]"


def log(content: str, clear_text: str = '') -> None:
    log_path = pathlib.Path(f'{len(user_data.user_names)}pl.log')
    if clear_text:
        log_path.write_text(clear_text, encoding='utf-8')
    with log_path.open(mode='a', encoding='utf-8') as file:
        file.write(content)


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
    badge: PBadge

    options: list[PPlayer]
    actors: list[PPlayer]
    died: list[PPlayer]
    data: dict[str, Any]

    def __init__(self) -> None:
        ...

    def __str__(self) -> str:
        ...

    def boardcast(
        self, pls: Iterable[PPlayer], content: str, source: str = 'Moderator'
    ) -> None:
        ...

    def unicast(
        self, pl: PPlayer, content: str, source: str = 'Moderator'
    ) -> None:
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


def seat2pl(game: PGame, seat: Seat) -> PPlayer:
    return game.players[seat]


def seats2pl(game: PGame, seats: Iterable[Seat]) -> Generator[PPlayer]:
    return (game.players[seat] for seat in seats)


class BaseGameError(Exception):
    ...


class SelfExposureError(Exception):
    ...
