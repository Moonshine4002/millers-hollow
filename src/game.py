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


class Time:
    class Phase(ModifiedEnum):
        NIGHT_MEET = auto()
        NIGHT = auto()
        DEBATE = auto()
        VOTE = auto()

    def __init__(self) -> None:
        self.cycle = 1
        self.phase = self.first()

    @classmethod
    def first(cls) -> Phase:
        return cls.Phase.NIGHT_MEET

    def next(self) -> None:
        match self.phase:
            case self.Phase.NIGHT_MEET:
                self.phase = self.Phase.NIGHT
            case self.Phase.NIGHT:
                self.phase = self.Phase.DEBATE
            case self.Phase.DEBATE:
                self.phase = self.Phase.VOTE
            case self.Phase.VOTE:
                self.phase = self.Phase.NIGHT_MEET
                self.cycle += 1
            case _:
                raise ValueError(f'wrong phase {self.phase!r}')


class Game:
    class PlayerInfo(NamedTuple):
        name: str
        role: Role
        seat: int

    game = None

    def __init__(self) -> None:
        cls = self.__class__
        if cls.game is None:
            cls.game = self
        else:
            raise RuntimeError(f'{cls.__name__} should be a Singleton')

        self.initialize([])

    def __str__(self) -> str:
        return (
            f'cycle={self.time.cycle}; '
            f'phase={self.time.phase}; '
            f'players=\n\t{"\n\t".join(str(i) for i in self.players)}'
        )

    def initialize(self, players_info: Sequence[PlayerInfo]) -> None:
        self.time = Time()
        self.players = [
            Player(player_info.name, player_info.role, player_info.seat)
            for player_info in players_info
        ]
        self.game_init()

    def game_init(self) -> None:
        for player in self.players:
            player.game_init()

    def loop(self) -> None:
        print(self)
        for player in self.players:
            player.assess()
            player.action()
        for player in self.players:
            player.execute()
            player.finalize()
        self.time.next()


game = Game()


class PProp:
    def __init__(
        self,
        seat: int,
        remain: int = 1,
        priority: int = 0,
        mask: int = 0,
    ) -> None:
        self.remain = remain
        self.used = False
        self.activate = False
        self.priority = priority
        self.mask = mask
        self.value = 1
        self.register(seat)

    def __str__(self) -> str:
        return f'{self.__class__.__name__}'

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

    def register(self, seat: int) -> None:
        self.source = game.players[seat]

    def aim(self, seat: int) -> None:
        assert self.source
        self.target = game.players[seat]

    def assess(self) -> None:
        self.value = 1
        for seat, attitude in enumerate(self.source.attitudes):
            match attitude:
                case Attitude.IGNORE:
                    pass
                case Attitude.ALLIED:
                    pass
                case Attitude.HOSTILE:
                    pass

    def action(self) -> None:
        match self.source.role:
            case Role.WEREWOLF:
                match game.time.phase:
                    case Time.Phase.NIGHT_MEET:
                        if self.__class__ == Meet:
                            self.attempt()
                    case Time.Phase.NIGHT:
                        if self.__class__ == Claw:
                            self.aim(0)
                            self.attempt()
            case Role.WITCH:
                if self.__class__ == Antidote:
                    self.aim(0)
                    self.attempt()
                elif self.__class__ == Poison:
                    self.aim(1)
                    self.attempt()
            case Role.HUNTER:
                self.aim(2)
                self.attempt()

    def validate(self) -> bool:
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
        if not self.validate():
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


class Meet(PProp):
    def __init__(self, seat: int) -> None:
        super().__init__(seat, -1)

    def validate(self) -> bool:
        if game.time.phase != Time.Phase.NIGHT_MEET:
            return False
        return super().validate()

    def _select(self) -> None:
        self.source.marks.append(self)

    def _effect(self) -> None:
        for player in game.players:
            if any(isinstance(prop, Meet) for prop in player.props):
                self.source.clues[player.seat].append('is werewolf')


class Claw(PProp):
    def __init__(self, seat: int) -> None:
        super().__init__(seat, -1)

    def validate(self) -> bool:
        if game.time.phase != Time.Phase.NIGHT:
            return False
        return super().validate()

    def _effect(self) -> None:
        self.target.life = False


class Crystal(PProp):
    def validate(self) -> bool:
        if game.time.phase != Time.Phase.NIGHT:
            return False
        return super().validate()

    def _effect(self) -> None:
        pass


class Poison(PProp):
    def __init__(self, seat: int) -> None:
        super().__init__(seat, 1, 2, 1)

    def validate(self) -> bool:
        if game.time.phase != Time.Phase.NIGHT:
            return False
        return super().validate()

    def _effect(self) -> None:
        self.target.life = False


class Antidote(PProp):
    def __init__(self, seat: int) -> None:
        super().__init__(seat, 1, 2, 1)

    def validate(self) -> bool:
        if game.time.phase != Time.Phase.NIGHT:
            return False
        return super().validate()

    def _effect(self) -> None:
        self.target.marks = list(
            filter(lambda mark: not isinstance(mark, Claw), self.target.marks)
        )


class Shotgun(PProp):
    def __init__(self, seat: int) -> None:
        super().__init__(seat, 1, 4)

    def _effect(self) -> None:
        self.target.life = False


class PPlayer:
    def __init__(self, name: str, role: Role, seat: int) -> None:
        self.name = name
        self.life = True
        self.role = role
        self.seat = seat
        self.props: list[PProp] = []
        self.marks: list[PProp] = []
        self.clues: list[list[Any]] = []
        self.attitudes: list[float] = []
        self.assumptions: list[dict[Role, float]] = []
        self.relationships: list[tuple[Attitude, float]] = []

    def __str__(self) -> str:
        return (
            f'{self.name}[{self.role}]{"†" if not self.life else ""}: '
            f'props={", ".join(str(i) for i in self.props)}; '
            f'marks={", ".join(str(i) for i in self.marks)}; '
            f'attitude={", ".join(str(i) for i in self.attitudes)}'
        )

    def game_init(self) -> None:
        match self.role:
            case Role.VILLAGER:
                pass
            case Role.WEREWOLF:
                self.props.append(Meet(self.seat))
                self.props.append(Claw(self.seat))
            case Role.SEER:
                self.props.append(Crystal(self.seat))
            case Role.WITCH:
                self.props.append(Poison(self.seat))
                self.props.append(Antidote(self.seat))
            case Role.HUNTER:
                self.props.append(Shotgun(self.seat))
            case _:
                warnings.warn(f'{self.role!r} has no props added silently')
        self.clues = [[] for player in game.players]
        self.attitudes = [0 for player in game.players]
        self.assumptions = [
            {role: 0 for role in Role} for player in game.players
        ]
        self.relationships = [(Attitude.IGNORE, 0) for player in game.players]
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
        for seat, p_clues in enumerate(self.clues):
            if any('is werewolf' in clue for clue in p_clues):
                if self.role & game.players[seat].role:
                    self.attitudes[seat] = 1
                else:
                    self.attitudes[seat] = -1
            elif any('is not werewolf' in clue for clue in p_clues):
                if self.role & game.players[seat].role:
                    self.attitudes[seat] = 1
                else:
                    self.attitudes[seat] = -1
        for seat, attitude in enumerate(self.attitudes):
            assumption = self.assumptions[seat]
            assumed_role = max(assumption, key=assumption.get)  # type: ignore[arg-type]
            if -1 <= attitude < -0.1:
                self.relationships[seat] = (Attitude.HOSTILE, abs(attitude))
            elif -0.1 <= attitude < 0.1:
                self.relationships[seat] = (Attitude.IGNORE, 1)
            elif 0.1 <= attitude <= 1:
                self.relationships[seat] = (Attitude.ALLIED, attitude)
            else:
                raise ValueError(f'wrong attitude value {attitude}')

        for prop in self.props:
            prop.assess()

    def action(self) -> None:
        for prop in self.props:
            prop.action()


class Player(PPlayer):
    ...
