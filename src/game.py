from .header import *


class Role(Enum):
    VILLAGER = auto()
    WEREWOLF = auto()
    SEER = auto()
    WITCH = auto()
    HUNTER = auto()

    def __str__(self):
        return f'{self.name.lower()}'


class PProp:
    def __init__(self, player: 'PPlayer', remain=1, priority=0, mask=0):
        self.remain = remain
        self.activate = False
        self.used = False
        self.priority = priority
        self.mask = mask
        self.register(player)

    def __str__(self):
        return f'{self.__class__.__name__}(prop)'

    def _compare(self, other, key: Callable[[Any, Any], bool]):
        if isinstance(other, PProp):
            return key(self.priority, other.priority)
        else:
            return NotImplemented

    def __eq__(self, other):
        return self._compare(other, lambda x, y: x == y)

    def __le__(self, other):
        return self._compare(other, lambda x, y: x <= y)

    def __lt__(self, other):
        return self._compare(other, lambda x, y: x < y)

    def register(self, player: 'PPlayer') -> None:
        self.source = player

    def aim(self, player: 'PPlayer') -> None:
        assert self.source
        self.target = player

    @abstractmethod
    def _validate(self) -> bool:
        if not self.source.life:
            return False
        if self.remain == 0:
            return False
        if self.mask != 0 and any(
            self.mask == prop.mask and prop.used for prop in self.source.props
        ):
            return False
        return True

    # @abstractmethod
    def _select(self) -> None:
        self.target.marks.append(self)

    def attempt(self) -> None:
        if not self._validate():
            return
        self.remain -= 1
        self.activate = True
        self.used = True
        self._select()

    @abstractmethod
    def _effect(self) -> None:
        ...

    def execute(self) -> None:
        self._effect()


class Claw(PProp):
    def __init__(self, player):
        super().__init__(player, -1)

    def _validate(self):
        if game.phase != game.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        self.target.life = False


class Crystal(PProp):
    def _validate(self):
        if game.phase != game.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        pass


class Poison(PProp):
    def __init__(self, player):
        super().__init__(player, 1, 2, 1)

    def _validate(self):
        if game.phase != game.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        self.target.life = False


class Antidote(PProp):
    def __init__(self, player):
        super().__init__(player, 1, 2, 1)

    def _validate(self):
        if game.phase != game.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        self.target.marks = list(
            filter(lambda mark: not isinstance(mark, Claw), self.target.marks)
        )


class Shotgun(PProp):
    def __init__(self, player):
        super().__init__(player, 1, 4)

    def _validate(self):
        return super()._validate()

    def _effect(self) -> None:
        self.target.life = False


class PPlayer:
    def __init__(self, name: str, role: Role):
        self.name = name
        self.life = True
        self.role = role
        self.props: list[PProp] = []
        match self.role:
            case Role.VILLAGER:
                pass
            case Role.WEREWOLF:
                self.props.append(Claw(self))
            case Role.SEER:
                self.props.append(Crystal(self))
            case Role.WITCH:
                self.props.append(Poison(self))
                self.props.append(Antidote(self))
            case Role.HUNTER:
                self.props.append(Shotgun(self))
            case _:
                warnings.warn(f'{self.role!r} has no props added silently')
        self.marks: list[PProp] = []

    def __str__(self):
        return (
            f'{self.name}[{self.role}]{"†" if not self.life else ""}: '
            f'props={", ".join(str(i) for i in self.props)}, '
            f'marks={", ".join(str(i) for i in self.marks)}'
        )


class Player(PPlayer):
    ...


class Game:
    class Phase(Enum):
        NIGHT = auto()
        DEBATE = auto()
        VOTE = auto()

        def __str__(self):
            return f'{self.name.lower()}'

    def __init__(self):
        self.init([])

    def init(self, players: list[PPlayer]) -> None:
        self.cycle = 1
        self.phase = self.Phase.NIGHT
        self.players = players

    def proceed(self) -> None:
        match self.phase:
            case self.Phase.NIGHT:
                for player in self.players:
                    player.marks.sort()  # reverse=True)
                    while player.marks:
                        mark = player.marks.pop()
                        mark.execute()
                for player in self.players:
                    for prop in player.props:
                        prop.used = False
                self.phase = self.Phase.DEBATE
            case self.Phase.DEBATE:
                self.phase = self.Phase.VOTE
            case self.Phase.VOTE:
                self.phase = self.Phase.NIGHT
                self.cycle += 1
            case _:
                raise ValueError(f'wrong phase {self.phase}')


game = Game()
