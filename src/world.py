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

        self.initialize()

    def initialize(self) -> None:
        self.players_info: list[Game.PlayerInfo] = []

        random.shuffle(self.players_role)
        for seat, role in enumerate(self.players_role):
            character = random.choice(self.character_pool)
            self.players_info.append(
                Game.PlayerInfo(character.name, role, seat)
            )

        game.initialize(self.players_info)

    def loop(self) -> None:
        game.loop()


world = World()
