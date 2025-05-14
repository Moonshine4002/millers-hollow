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
    world = None

    def __init__(self) -> None:
        cls = self.__class__
        if cls.world is None:
            cls.world = self
        else:
            raise RuntimeError(f'{cls.__name__} should be a Singleton')

        self.character_pool_num = 100
        self.players_role = [
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

        self.character_pool = [
            Character(str(i)) for i in range(self.character_pool_num)
        ]
        self.characters: list[Character] = []
        self.players: list[Player] = []

        self.start_game()

    def start_game(self) -> None:
        random.shuffle(self.players_role)
        for role in self.players_role:
            character = random.choice(self.character_pool)
            self.characters.append(character)
            self.players.append(Player(character.name, role))
        game.init(self.players)
        game.prepare()

    def __str__(self) -> str:
        return (
            f'cycle={game.cycle}; '
            f'phase={game.phase}; '
            f'players=\n\t{"\n\t".join(str(i) for i in self.players)}'
        )

    def game_loop(self) -> None:
        print(self)

        game.action()
        for i in self.players:
            match i.role:
                case Role.WEREWOLF:
                    i.props[0].aim(self.players[0])
                    i.props[0].attempt()
                case Role.WITCH:
                    i.props[1].aim(self.players[0])
                    i.props[1].attempt()
                    i.props[0].aim(self.players[1])
                    i.props[0].attempt()
                case Role.HUNTER:
                    i.props[0].aim(self.players[2])
                    i.props[0].attempt()

        print(self)

        game.proceed()
        game.proceed()
        game.proceed()


world = World()
