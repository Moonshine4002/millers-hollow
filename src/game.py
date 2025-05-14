from .header import *

from .utility import *


class Role(ModifiedEnum):
    VILLAGER = 1
    WEREWOLF = -1
    SEER = 2
    WITCH = 3
    HUNTER = 4

    def __and__(self, other: Any) -> bool:
        if isinstance(other, Role):
            if self.value * other.value == 0:
                if self.value + other.value == 0:
                    return True
                else:
                    return False
            elif self.value * other.value > 0:
                return True
            else:
                return False
        else:
            return NotImplemented


class Attitude(ModifiedEnum):
    IGNORE = auto()
    ALLIED = auto()
    HOSTILE = auto()
    COMPETITIVE = auto()
    DECEPTIVE = auto()


class Game:
    class Phase(ModifiedEnum):
        NIGHT = auto()
        DEBATE = auto()
        VOTE = auto()

    def __init__(self) -> None:
        self.init([])

    def init(self, players: Sequence['PPlayer']) -> None:
        self.cycle = 1
        self.phase = self.Phase.NIGHT
        self.players = list(players)

    def prepare(self) -> None:
        for player in self.players:
            player.clear()

    def action(self) -> None:
        for player in self.players:
            player.assess()

    def proceed(self) -> None:
        match self.phase:
            case self.Phase.NIGHT:
                for player in self.players:
                    player.execute()
                for player in self.players:
                    player.finalize()
                self.phase = self.Phase.DEBATE
            case self.Phase.DEBATE:
                self.phase = self.Phase.VOTE
            case self.Phase.VOTE:
                for player in self.players:
                    player.execute()
                for player in self.players:
                    player.finalize()
                self.phase = self.Phase.NIGHT
                self.cycle += 1
            case _:
                raise ValueError(f'wrong phase {self.phase}')


game = Game()


class PProp:
    def __init__(
        self,
        player: 'PPlayer',
        remain: int = 1,
        priority: int = 0,
        mask: int = 0,
    ) -> None:
        self.remain = remain
        self.used = False
        self.activate = False
        self.priority = priority
        self.mask = mask
        self.register(player)
        self._calculate()

    def __str__(self) -> str:
        return f'{self.__class__.__name__}(prop)'

    def _compare(self, other: Any, key: Callable[[Any, Any], bool]) -> bool:
        if isinstance(other, PProp):
            return key(self.priority, other.priority)
        else:
            return NotImplemented

    def __eq__(self, other: Any) -> bool:
        return self._compare(other, lambda x, y: x == y)

    def __le__(self, other: Any) -> bool:
        return self._compare(other, lambda x, y: x <= y)

    def __lt__(self, other: Any) -> bool:
        return self._compare(other, lambda x, y: x < y)

    def register(self, player: 'PPlayer') -> None:
        self.source = player

    def aim(self, player: 'PPlayer') -> None:
        assert self.source
        self.target = player

    # @abstractmethod
    def _calculate(self) -> None:
        self.value = 1

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
        self._calculate()
        if not self._validate():
            return
        self.remain -= 1
        self.used = True
        self.activate = True
        self._select()

    @abstractmethod
    def _effect(self) -> None:
        ...

    def execute(self) -> None:
        self._effect()


class Claw(PProp):
    def __init__(self, player: 'PPlayer') -> None:
        super().__init__(player, -1)

    def _validate(self) -> bool:
        if game.phase != game.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        self.target.life = False


class Crystal(PProp):
    def _validate(self) -> bool:
        if game.phase != game.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        pass


class Poison(PProp):
    def __init__(self, player: 'PPlayer') -> None:
        super().__init__(player, 1, 2, 1)

    def _validate(self) -> bool:
        if game.phase != game.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        self.target.life = False


class Antidote(PProp):
    def __init__(self, player: 'PPlayer') -> None:
        super().__init__(player, 1, 2, 1)

    def _validate(self) -> bool:
        if game.phase != game.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        self.target.marks = list(
            filter(lambda mark: not isinstance(mark, Claw), self.target.marks)
        )


class Shotgun(PProp):
    def __init__(self, player: 'PPlayer') -> None:
        super().__init__(player, 1, 4)

    def _validate(self) -> bool:
        return super()._validate()

    def _effect(self) -> None:
        self.target.life = False


class PPlayer:
    def __init__(self, name: str, role: Role) -> None:
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
        self.attitude: dict[str, float] = {}
        self.assumption: dict[str, dict[Role, float]] = {}
        self.relationship: dict[str, tuple[Attitude, float]] = {}

    def __str__(self) -> str:
        return (
            f'{self.name}[{self.role}]{"†" if not self.life else ""}: '
            f'props={", ".join(str(i) for i in self.props)}, '
            f'marks={", ".join(str(i) for i in self.marks)}'
        )

    def clear(self) -> None:
        self.marks = []
        self.attitude = {player.name: 0 for player in game.players}
        self.assumption = {
            player.name: {role: 0 for role in Role} for player in game.players
        }
        self.relationship = {
            player.name: (Attitude.IGNORE, 0) for player in game.players
        }
        self.assess()

    def execute(self) -> None:
        self.marks.sort()  # reverse=True)
        while self.marks:
            mark = self.marks.pop()
            mark.execute()

    def finalize(self) -> None:
        for prop in self.props:
            prop.used = False

    def deactive(self) -> None:
        for prop in self.props:
            prop.activate = False

    def assess(self) -> None:
        for pid, attitude in self.attitude.items():
            assumption = self.assumption[pid]
            assumed_role = max(assumption, key=assumption.get)  # type: ignore[arg-type]
            if -1 <= attitude < -0.1:
                self.relationship[pid] = (Attitude.HOSTILE, abs(attitude))
            elif -0.1 <= attitude < 0.1:
                self.relationship[pid] = (Attitude.IGNORE, 1)
            elif 0.1 <= attitude <= 1:
                self.relationship[pid] = (Attitude.ALLIED, attitude)
            else:
                raise ValueError(f'wrong attitude value {attitude}')


class Player(PPlayer):
    ...
