from src.header import *
from src.world import World


World.start_game()
while True:
    time.sleep(0.1)
    World.game_loop()
