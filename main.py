from src.player import *

chars: list[Char] = user_data.chars
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
