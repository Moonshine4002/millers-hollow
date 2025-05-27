from header import *


@dataclass
class InfoCharacter:
    name: str


Seat: TypeAlias = int


class Faction:
    _id = 0

    def __init__(self, name: str) -> None:
        cls = self.__class__
        self._id = cls._id
        cls._id += 1

        self.name = name

    def __str__(self) -> str:
        return self.name


faction_villager = Faction('villager')
faction_werewolf = Faction('werewolf')


@dataclass
class InfoRole:
    seat: Seat
    faction: Faction = faction_villager


class PPlayer(Protocol):
    life: bool
    seat: Seat
    faction: Faction

    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        ...


class PGame(Protocol):
    players: list[PPlayer]


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
        role.faction = faction_werewolf
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
    ]

    def __init__(self) -> None:
        self.players: list[PPlayer] = []
        random.shuffle(self.roles)

        for seat, role in enumerate(self.roles):
            self.players.append(role(self.characters[seat], InfoRole(seat)))

    def __str__(self) -> str:
        return 'players: \n\t' + '\n\t'.join(
            str(player) for player in game.players
        )


game = Game()
print(game)
