from header import *
from utility import *


@dataclass
class InfoCharacter:
    name: str

    def __str__(self) -> str:
        return f'{self.name}'


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
            return self.eq_category(value) and self.eq_category(value)
        return NotImplemented


Role: TypeAlias = str


@dataclass
class InfoRole:
    seat: Seat
    faction: Faction = field(default_factory=Faction)
    role: Role = 'blank'

    def __str__(self) -> str:
        return f'{self.role}'


class Phase(NamedEnum):
    NIGHT = auto()
    DAY = auto()

    FIRST = NIGHT

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
    cycle: int
    phase: Phase
    round: int = 1

    def __str__(self) -> str:
        return f'{self.cycle}:{self.phase}:{self.round}'

    def inc_phase(self) -> None:
        self.phase = next(self.phase)
        if self.phase == Phase.FIRST:
            self.cycle += 1
            self.round = 0

    def inc_round(self) -> None:
        self.round += 1


class Clue(NamedTuple):
    time: Time
    clue: str


class PPlayer(Protocol):
    life: bool
    character: InfoCharacter
    role: InfoRole
    clues: list[Clue]

    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        ...


class PGame(Protocol):
    players: list[PPlayer]
    time: Time


"""
Factions:
Faction('villager')
Faction('werewolf')
Faction('villager', 'god')
"""


class BPlayer:
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        self.life = True
        self.character = character
        self.role = role
        self.role.role = self.__class__.__name__.lower()
        self.clues: list[Clue] = []

    def __str__(self) -> str:
        life = '☥' if self.life else '†'
        return f'{life}{self.character}[{self.role}]: {self.clues}'

    def choose(self, candidates: Sequence[Seat]) -> Seat:
        return 0


class Villager(BPlayer):
    ...


class Werewolf(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction.faction = 'werewolf'
        super().__init__(character, role)


class Seer(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction.category = 'god'
        super().__init__(character, role)


class Game:
    characters = [
        InfoCharacter('A'),
        InfoCharacter('B'),
        InfoCharacter('C'),
        InfoCharacter('D'),
        InfoCharacter('E'),
        InfoCharacter('F'),
        InfoCharacter('G'),
        InfoCharacter('H'),
        InfoCharacter('I'),
    ]

    roles: list[type[PPlayer]] = [
        Villager,
        Villager,
        Villager,
        Werewolf,
        Werewolf,
        Werewolf,
        Seer,
    ]

    def __init__(self) -> None:
        self.players: list[PPlayer] = []
        random.shuffle(self.roles)

        for seat, role in enumerate(self.roles):
            self.players.append(role(self.characters[seat], InfoRole(seat)))

        self.time = Time(1, Phase.NIGHT)

    def __str__(self) -> str:
        info_player = '\n\t'.join(str(player) for player in game.players)
        info_time = str(self.time)
        return f'[{info_time}]players: \n\t{info_player}'

    def winner(self) -> Faction:
        count_villagers = 0
        count_werewolfs = 0
        count_god = 0
        for player in self.players:
            if not player.life:
                continue
            match player.role.faction:
                case Faction('villager', 'standard'):
                    count_villagers += 1
                case Faction('werewolf'):
                    count_werewolfs += 1
                case Faction('villager', 'god'):
                    count_god += 1
                case _:
                    raise NotImplementedError('unknown faction')
        if count_villagers + count_werewolfs + count_god == 0:
            return Faction('nobody')
        elif count_villagers + count_god == 0:   # count_villagers * count_god
            return Faction('werewolf')
        elif count_werewolfs == 0:
            return Faction('villager')
        # elif count_villagers + count_god < count_werewolfs:
        #    return Faction('werewolf')
        else:
            return Faction('')


game = Game()
print(game)
winner = game.winner()
if winner:
    print(winner, 'win')
    print(
        'winners:\n\t'
        + '\n\t'.join(
            str(player)
            for player in game.players
            if winner.eq_faction(player.role.faction)
        )
    )
else:
    print('not yet')
