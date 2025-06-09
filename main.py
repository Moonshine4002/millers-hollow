from src.player import *

chars = [Char(name, 'ai') for name in string.ascii_uppercase]
roles = [
    Villager,
    Villager,
    Villager,
    Werewolf,
    Werewolf,
    Werewolf,
    Seer,
    Witch,
    Fool,
]
game = Game(chars, roles)

game.loop()
