import pytest

import sys
import pathlib

BASE_DIR = str(pathlib.Path(__file__).parent.parent)
sys.path.append(BASE_DIR)
from src.world import *


class TestGame:
    def game_loop(self):
        for player in game.players:
            match game.time.phase:
                case Time.Phase.NIGHT_MEET:
                    match player.role:
                        case Role.VILLAGER:
                            player.assess()
                        case Role.WEREWOLF:
                            player.assess()
                        case Role.SEER:
                            player.assess()
                        case Role.WITCH:
                            player.assess()
                        case Role.HUNTER:
                            player.assess()
                case Time.Phase.NIGHT:
                    match player.role:
                        case Role.VILLAGER:
                            player.assess()
                        case Role.WEREWOLF:
                            player.props[1].aim(0)
                        case Role.SEER:
                            player.assess()
                        case Role.WITCH:
                            pass
                        case Role.HUNTER:
                            player.assess()
                case Time.Phase.DEBATE:
                    match player.role:
                        case Role.VILLAGER:
                            player.assess()
                        case Role.WEREWOLF:
                            player.assess()
                        case Role.SEER:
                            player.assess()
                        case Role.WITCH:
                            player.assess()
                        case Role.HUNTER:
                            player.assess()
                case Time.Phase.VOTE:
                    match player.role:
                        case Role.VILLAGER:
                            player.assess()
                        case Role.WEREWOLF:
                            player.assess()
                        case Role.SEER:
                            player.assess()
                        case Role.WITCH:
                            player.assess()
                        case Role.HUNTER:
                            player.assess()
            player.action()
        print(self)
        for player in game.players:
            player.execute()
            player.finalize()
        game.time.next()

    def test_game_loop(self):
        self.game_loop()
        self.game_loop()
        assert not game.players[0].life
        self.game_loop()
        self.game_loop()


if __name__ == '__main__':
    pytest.main()
