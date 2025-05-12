from .header import *

from .game import *


class Character:
    def __init__(self, name: str):
        self.name = name
        self.win = 0
        self.lose = 0

    def __repr__(self):
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
    def start_game(cls):
        random.shuffle(cls.players_role)
        for role in cls.players_role:
            character = random.choice(cls.character_pool)
            cls.characters.append(character)
            cls.players.append(Player(character.name, role))
        game.init(cls.players)

    @classmethod
    def game_loop(cls):
        print(f'players=\n\t{"\n\t".join(str(i) for i in cls.players)}')

        print(f'cycle={game.cycle}')

        for i in cls.players:
            match i.role:
                case Role.WEREWOLF:
                    i.props[0].aim(cls.players[0])
                    i.props[0].attempt()
                case Role.WITCH:
                    i.props[0].aim(cls.players[1])
                    i.props[0].attempt()
                    i.props[1].aim(cls.players[0])
                    i.props[1].attempt()
                case Role.HUNTER:
                    i.props[0].aim(cls.players[2])
                    i.props[0].attempt()

        game.proceed()
        game.proceed()
        game.proceed()
