from header import *


@dataclass
class InfoCharacter:
    name: str


Seat: TypeAlias = int


class Faction:
    _instances: dict[tuple[str, str], Self] = {}
    # __match_args__ = (f'_{__qualname__}__faction', f'{__qualname__}__category')  # type: ignore

    def __new__(cls, faction: str, category: str = 'standard') -> Self:
        key = (faction, category)
        if key in cls._instances:
            return cls._instances[key]
        instance = super().__new__(cls)
        cls._instances[key] = instance
        return instance

    def __init__(self, faction: str, category: str = 'standard') -> None:
        self.__faction = faction
        self.__category = category

    def __str__(self) -> str:
        return self.__faction

    def __bool__(self) -> bool:
        return bool(self.__faction)

    def __eq__(self, value: Any) -> bool:
        if isinstance(value, self.__class__):
            return self.__faction == value.__faction
        return NotImplemented


@dataclass
class InfoRole:
    seat: Seat
    faction: Faction


class PPlayer(Protocol):
    life: bool
    seat: Seat
    faction: Faction

    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        ...


class PGame(Protocol):
    players: list[PPlayer]


"""
Factions:
Faction('villager')
Faction('werewolf')
Faction('villager', 'god')
"""


class BPlayer:
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        self.life = True
        self.name = character.name
        self.seat = role.seat
        self.faction = role.faction

    def __str__(self) -> str:
        life = '☥' if self.life else '†'
        role = self.__class__.__name__
        return f'{life}{self.name}[{role}]'


class Villager(BPlayer):
    ...


class Werewolf(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction = Faction('werewolf')
        super().__init__(character, role)


class Seer(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction = Faction('villager', 'god')
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
            self.players.append(
                role(
                    self.characters[seat], InfoRole(seat, Faction('villager'))
                )
            )

    def __str__(self) -> str:
        return 'players: \n\t' + '\n\t'.join(
            str(player) for player in game.players
        )

    def winner(self) -> Faction:
        count_villagers = 0
        count_werewolfs = 0
        count_god = 0
        for player in self.players:
            match player.faction:
                case x if x is Faction('villager', 'standard'):
                    count_villagers += 1
                case x if x is Faction('werewolf'):
                    count_werewolfs += 1
                case x if x is Faction('villager', 'god'):
                    count_god += 1
                case _:
                    raise NotImplementedError('unknown faction')
        if count_villagers + count_god == 0:
            return Faction('werewolf')
        elif count_werewolfs == 0:
            return Faction('villager')
        elif count_villagers + count_god < count_werewolfs:
            return Faction('werewolf')
        else:
            return Faction('')


game = Game()
print(game)
winner = game.winner()
if winner:
    print(winner, 'win')
else:
    print('not yet')
