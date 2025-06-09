from src.player import *

from src import user_mod

chars: list[Char] = user_mod.chars
roles: list[type[PPlayer]] = user_mod.roles

game = Game(chars, roles)

game.loop()
