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


class Relationship(ModifiedEnum):
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


Seat: TypeAlias = int


class Game:
    class PlayerInfo(NamedTuple):
        name: str
        role: Role
        seat: Seat

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
        for player in self.players:
            player.assess()
            player.action()
        print(self)
        for player in self.players:
            player.execute()
            player.finalize()
        self.time.next()


game = Game()


class PProp:
    @dataclass
    class Candidate:
        candidates: dict[Seat, float]
        options: list[Seat] | None = None

        def clear(self) -> None:
            self.candidates.clear()
            self.options = None

        def max(self) -> list[Seat]:
            filtered_candidates = {
                seat: value
                for seat, value in self.candidates.items()
                if self.options is None or seat in self.options
            }
            if not filtered_candidates:
                return []
            max_value = max(filtered_candidates.values())
            return [
                seat
                for seat, value in filtered_candidates.items()
                if value == max_value
            ]

    class Mark(UserDict[str, 'PProp']):
        def __str__(self) -> str:
            return ', '.join(
                cls_name
                if prop.quantity == 1
                else f'{cls_name}({prop.quantity})'
                for cls_name, prop in self.items()
            )

        def get_quantity(self, key: str, default: float = 0) -> float:
            try:
                return self[key].quantity
            except KeyError:
                return default

        def append(self, prop: 'PProp') -> None:
            cls_name = str(prop)
            if cls_name not in self:
                self[cls_name] = copy.copy(prop)
            else:
                self[cls_name] += prop

        def remove(self, key: str) -> None:
            try:
                del self[key]
            except KeyError:
                pass

        def execute(self) -> None:
            while self:
                prior = max(self, key=self.get_quantity)
                prop = self[prior]
                prop.execute()
                self.remove(prior)

        def max_quantity_seats(self, prop_type: type) -> list[Seat]:
            quantity_seat: list[tuple[float, Seat]] = []
            for player in game.players:
                seat = player.seat
                quantity = player.marks.get_quantity(prop_type.__name__)
                if quantity == 0:
                    continue
                quantity_seat.append((quantity, seat))
            if not quantity_seat:
                return []
            max_quantity = max(quantity_seat)[0]
            return [
                seat
                for quantity, seat in quantity_seat
                if quantity == max_quantity
            ]

    def __init__(
        self,
        seat: Seat,
        remain: int = 1,
        priority: int = 0,
        mask: int = 0,
        quantity: float = 1,
    ) -> None:
        self.remain = remain
        self.used = False
        self.activate = False
        self.priority = priority
        self.mask = mask
        self.quantity = quantity
        self.value = 1
        self.register(seat)
        self.aim(seat)
        self.candidates: PProp.Candidate = PProp.Candidate({})

    def __str__(self) -> str:
        return f'{self.__class__.__name__}'

    def __iadd__(self, other: Any) -> Self:
        if isinstance(other, PProp):
            self.quantity += other.quantity
        else:
            return NotImplemented
        return self

    def register(self, seat: Seat) -> None:
        self.source = game.players[seat]

    def aim(self, seat: Seat) -> None:
        self.target = game.players[seat]

    def _assess_ignore(self, seat: Seat, intensity: float) -> None:
        self.candidates.candidates[seat] = intensity

    def _assess_allied(self, seat: Seat, intensity: float) -> None:
        pass  # self.candidate.candidates[seat] = 0

    def _assess_hostile(self, seat: Seat, intensity: float) -> None:
        self.candidates.candidates[seat] = 1 + intensity

    def assess(self) -> None:
        self.value = 1
        self.candidates.candidates.clear()
        self.candidates.options = [
            player.seat for player in game.players if player.life
        ]   # TODO: use clue instead
        for seat, (relationship, intensity) in enumerate(
            self.source.relationships
        ):
            match relationship:
                case Relationship.IGNORE:
                    self._assess_ignore(seat, intensity)
                case Relationship.ALLIED:
                    self._assess_allied(seat, intensity)
                case Relationship.HOSTILE:
                    self._assess_hostile(seat, intensity)
        seats = self.candidates.max()
        for seat in seats:   # TODO
            self.aim(seats[0])
            if self._validate():
                break

    # @abstractmethod
    def _validate(self) -> bool:
        if not self.source.life:
            return False
        if self.remain == 0:
            return False
        if self.mask != 0 and any(
            self.mask == prop.mask and prop.used for prop in self.source.props
        ):
            return False
        if (
            self.candidates.options is not None
            and self.target.seat not in self.candidates.candidates
        ):
            return False
        return True

    # @abstractmethod
    def _select(self) -> None:
        self.target.marks.append(self)

    def action(self) -> bool:
        if not self._validate():
            return False
        self.remain -= 1
        self.used = True
        self.activate = True
        self._select()
        return True

    @abstractmethod
    def _effect(self) -> None:
        ...

    def execute(self) -> None:
        self._effect()


class Vote(PProp):
    def __init__(self, seat: Seat) -> None:
        super().__init__(seat, -1)

    def _validate(self) -> bool:
        if game.time.phase != Time.Phase.VOTE:
            return False
        return super()._validate()

    def _effect(self) -> None:
        candidates = PProp.Candidate(
            {
                player.seat: player.marks.get_quantity(str(self))
                for player in game.players
            },
            [player.seat for player in game.players if player.life],
        )
        options = candidates.max()
        if len(options) == 0:
            return
        if len(options) == 1:
            game.players[options[0]].life = False
        else:
            for player in game.players:
                for prop in player.props:
                    if not isinstance(prop, Vote):
                        continue
                    prop.candidates.options = options
                player.marks.remove(str(self))
            for player in game.players:
                player.assess()
                player.action()

            candidates.candidates = {
                player.seat: player.marks.get_quantity(str(self))
                for player in game.players
            }
            candidates.options = options
            options = candidates.max()
            if len(options) == 0:
                return
            if len(options) == 1:
                game.players[options[0]].life = False
            else:
                pass

        for player in game.players:
            player.marks.remove(str(self))


class Meet(PProp):
    def __init__(self, seat: Seat) -> None:
        super().__init__(seat, -1)

    def _validate(self) -> bool:
        if game.time.phase != Time.Phase.NIGHT_MEET:
            return False
        return super()._validate()

    def _select(self) -> None:
        self.source.marks.append(self)

    def _effect(self) -> None:
        for player in game.players:
            if any(isinstance(prop, Meet) for prop in player.props):
                self.source.clues[player.seat].append('is werewolf')


class Claw(PProp):
    def __init__(self, seat: Seat) -> None:
        super().__init__(seat, -1)

    def _validate(self) -> bool:
        if game.time.phase != Time.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        self.target.life = False


class Crystal(PProp):
    def __init__(self, seat: Seat) -> None:
        super().__init__(seat, -1)

    def _validate(self) -> bool:
        if game.time.phase != Time.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        seat = self.target.seat
        if self.source.role & self.target.role:
            self.source.clues[seat].append('is not werewolf')
        else:
            self.source.clues[seat].append('is werewolf')

    def _assess_ignore(self, seat: Seat, intensity: float) -> None:
        self.candidates.candidates[seat] = 3 - intensity

    def _assess_allied(self, seat: Seat, intensity: float) -> None:
        self.candidates.candidates[seat] = 2 - intensity

    def _assess_hostile(self, seat: Seat, intensity: float) -> None:
        self.candidates.candidates[seat] = 1 - intensity


class Poison(PProp):
    def __init__(self, seat: Seat) -> None:
        super().__init__(seat, 1, 2, 1)

    def _validate(self) -> bool:
        if game.time.phase != Time.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        self.target.life = False


class Antidote(PProp):
    def __init__(self, seat: Seat) -> None:
        super().__init__(seat, 1, 2, 1)

    def _validate(self) -> bool:
        # TODO: check Claw
        if game.time.phase != Time.Phase.NIGHT:
            return False
        return super()._validate()

    def _effect(self) -> None:
        self.target.marks.remove(Claw.__name__)


class Shotgun(PProp):
    def __init__(self, seat: Seat) -> None:
        super().__init__(seat, 1, 4)

    def _effect(self) -> None:
        self.target.life = False


class PPlayer:
    def __init__(self, name: str, role: Role, seat: Seat) -> None:
        self.name = name
        self.life = True
        self.role = role
        self.seat = seat
        self.props: list[PProp] = []
        self.marks: PProp.Mark = PProp.Mark()
        self.clues: list[list[Any]] = []  # TODO: refactor clue
        self.attitudes: list[float] = []
        self.assumptions: list[dict[Role, float]] = []
        self.relationships: list[tuple[Relationship, float]] = []

    def __str__(self) -> str:
        return (
            f'{self.name}[{self.role}]{"†" if not self.life else ""}: '
            f'props={", ".join(str(i) for i in self.props)}; '
            f'marks={self.marks}; '
            f'attitude={", ".join(str(i) for i in self.attitudes)}'
        )

    def game_init(self) -> None:
        self.props.append(Vote(self.seat))
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
                warnings.warn(f'{self.role} has no props added silently')
        self.clues = [[] for player in game.players]
        self.attitudes = [0 for player in game.players]
        self.assumptions = [
            {role: 0 for role in Role} for player in game.players
        ]
        self.relationships = [
            (Relationship.IGNORE, 0) for player in game.players
        ]

    def assess(self) -> None:
        self.attitudes[self.seat] = 1
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
            # TODO: assumption
            assumption = self.assumptions[seat]
            assumed_role = max(assumption, key=assumption.get)  # type: ignore[arg-type]
            if -1 <= attitude < -0.1:
                self.relationships[seat] = (
                    Relationship.HOSTILE,
                    abs(attitude),
                )
            elif -0.1 <= attitude < 0.1:
                self.relationships[seat] = (Relationship.IGNORE, 1)
            elif 0.1 <= attitude <= 1:
                self.relationships[seat] = (Relationship.ALLIED, attitude)
            else:
                raise ValueError(f'wrong attitude value {attitude}')

        for prop in self.props:
            prop.assess()

    def action(self) -> None:
        for prop in self.props:
            prop.action()

    def execute(self) -> None:
        self.marks.execute()

    def finalize(self) -> None:
        for prop in self.props:
            prop.used = False

    def deactive(self) -> None:
        for prop in self.props:
            prop.activate = False


class Player(PPlayer):
    ...
