from .header import *

from .game import *


class Character:
    def __init__(self, name: str) -> None:
        self.name = name
        self.win = 0
        self.lose = 0

    def __str__(self) -> str:
        return f'{self.name}({self.win}-{self.lose})'


class World:
    character_pool_num = 100
    players_role = [
        Role.VILLAGER,
        Role.VILLAGER,
        Role.VILLAGER,
        Role.WEREWOLF,
        Role.WEREWOLF,
        Role.WEREWOLF,
        Role.SEER,
        Role.WITCH,
        Role.HUNTER,
    ]

    character_pool = [Character(str(i)) for i in range(character_pool_num)]
    characters: list[Character] = []
    players: list[Player] = []

    @classmethod
    def start_game(cls) -> None:
        random.shuffle(cls.players_role)
        for role in cls.players_role:
            character = random.choice(cls.character_pool)
            cls.characters.append(character)
            cls.players.append(Player(character.name, role))
        game.init(cls.players)
        game.prepare()

    @classmethod
    def print(cls) -> None:
        print(
            f'cycle={game.cycle}; '
            f'phase={game.phase}; '
            f'players=\n\t{"\n\t".join(str(i) for i in cls.players)}'
        )

    @classmethod
    def game_loop(cls) -> None:
        cls.print()

        game.action()
        for i in cls.players:
            match i.role:
                case Role.WEREWOLF:
                    i.props[0].aim(cls.players[0])
                    i.props[0].attempt()
                case Role.WITCH:
                    i.props[1].aim(cls.players[0])
                    i.props[1].attempt()
                    i.props[0].aim(cls.players[1])
                    i.props[0].attempt()
                case Role.HUNTER:
                    i.props[0].aim(cls.players[2])
                    i.props[0].attempt()

        cls.print()

        game.proceed()
        game.proceed()
        game.proceed()
