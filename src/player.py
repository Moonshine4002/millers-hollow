from .utility import *

from .ai.ai import get_seat, get_speech


@dataclass
class InfoCharacter:
    name: str
    control: str = 'input'


Seat: TypeAlias = int


class Faction:
    __match_args__ = ('faction', 'category')

    def __init__(
        self, faction: str = 'villager', category: str = 'standard'
    ) -> None:
        self.faction = faction
        self.category = category

    def __str__(self) -> str:
        return self.faction + (
            '-' + self.category if self.category != 'standard' else ''
        )

    def __bool__(self) -> bool:
        return bool(self.faction)

    def eq_faction(self, value: Self) -> bool:
        return self.faction == value.faction

    def eq_category(self, value: Self) -> bool:
        return self.category == value.category

    def __eq__(self, value: Any) -> bool:
        if isinstance(value, self.__class__):
            return self.eq_faction(value) and self.eq_category(value)
        return NotImplemented


Role: TypeAlias = str


@dataclass
class InfoRole:
    seat: Seat
    faction: Faction = field(default_factory=Faction)
    role: Role = 'blank'


class Phase(NamedEnum):
    NIGHT = auto()
    DAY = auto()

    FIRST = NIGHT
    LAST = DAY

    def __next__(self) -> Self:
        match self:
            case self.DAY:
                return self.NIGHT
            case self.NIGHT:
                return self.DAY
            case _:
                raise NotImplementedError('unknown phase')


@dataclass
class Time:
    cycle: int = 0
    phase: Phase = Phase.LAST
    round: int = 0

    def __str__(self) -> str:
        return f'{self.cycle}:{self.phase}:{self.round}'

    def inc_phase(self) -> None:
        self.round = 0
        self.phase = next(self.phase)
        if self.phase == Phase.FIRST:
            self.cycle += 1

    def inc_round(self) -> None:
        self.round += 1


class Mark(NamedTuple):
    name: str
    source: Seat
    target: Seat
    func: Callable[[Seat, Seat], None]
    priority: int = 0

    def exec(self) -> None:
        self.func(self.source, self.target)


class Clue(NamedTuple):
    time: Time
    source: Seat | None
    clue: str

    def __str__(self) -> str:
        return f'"[{self.time}]{self.source if self.source is not None else "Moderator"}> {self.clue}"'


class PPlayer(Protocol):
    life: bool
    character: InfoCharacter
    role: InfoRole
    clues: list[Clue]

    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        ...

    def mark(self, target: Seat) -> Mark:
        ...

    def choose(self, candidates: Sequence[Seat]) -> Seat:
        ...

    def boardcast(self, audiences: Sequence[Seat], content: str) -> None:
        ...

    def text_clues(self) -> str:
        ...


class PGame(Protocol):
    time: Time
    players: list[PPlayer]
    marks: list[Mark]


"""
Factions:
Faction('villager')
Faction('werewolf')
Faction('villager', 'god')
"""


class BPlayer:
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        self.life = True
        self.character = character
        self.role = role
        self.role.role = self.__class__.__name__.lower()
        self.clues: list[Clue] = []

    def __str__(self) -> str:
        life = '☥' if self.life else '†'
        clues = ', '.join(str(clue) for clue in self.clues)
        return f'{life}{self.character.name}(seat {self.role.seat})[{self.role.role}]'

    def mark(self, target: Seat) -> Mark:
        return Mark(
            self.role.role, self.role.seat, target, lambda source, target: None
        )

    def choose(self, candidates: Sequence[Seat]) -> Seat:
        candidate: Seat = -1
        while candidate not in candidates:
            try:
                match self.character.control:
                    case 'input':
                        candidate = Seat(input(f'{self.role.seat}> '))
                    case 'ai':
                        candidate = Seat(
                            get_seat(
                                self.text_clues(),
                                self.role.seat,
                                self.role.role,
                            )
                        )
                    case _:
                        raise NotImplementedError('unknown control')
            except Exception as e:
                log(str(e))
        return candidate

    def boardcast(self, audiences: Sequence[Seat], content: str) -> None:
        log(f'{self.role.seat}> {content} > {audiences}')
        for seat in audiences:
            player = game.players[seat]
            player.clues.append(Clue(copy(game.time), self.role.seat, content))
            if player.character.control == 'input':
                print(f'{self.role.seat}> {content}')

    def text_clues(self) -> str:
        dialogues = '\n'.join(
            f'{clue.source if clue.source is not None else "Moderator"}> {clue.clue}'
            for clue in self.clues
        )
        return (
            f'Your info:\n- Your name: {self.character.name}.\n- Your seat: {self.role.seat}.\n- Your role: {self.role.role}.\n'
            f'Dialogues:\n{dialogues}'
        )


class Villager(BPlayer):
    ...


class Werewolf(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction.faction = 'werewolf'
        super().__init__(character, role)

    def mark(self, target: Seat) -> Mark:
        def func(source: Seat, target: Seat) -> None:
            game.players[target].life = False

        return Mark(self.role.role, self.role.seat, target, func)


class Seer(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction.category = 'god'
        super().__init__(character, role)


class Game:
    characters = [
        InfoCharacter('A', 'ai'),
        InfoCharacter('B', 'ai'),
        InfoCharacter('C', 'ai'),
        InfoCharacter('D', 'ai'),
        InfoCharacter('E', 'ai'),
        InfoCharacter('F', 'ai'),
        InfoCharacter('G', 'ai'),
        InfoCharacter('H', 'ai'),
        InfoCharacter('I', 'ai'),
    ]

    roles: list[type[PPlayer]] = [
        Villager,
        Villager,
        Villager,
        Werewolf,
        Werewolf,
        Werewolf,
        Seer,
        Villager,
        Villager,
    ]

    def __init__(self) -> None:
        self.time = Time()
        self.players: list[PPlayer] = []
        self.marks: list[Mark] = []

        random.shuffle(self.characters)
        random.shuffle(self.roles)
        for seat, role in enumerate(self.roles):
            self.players.append(role(self.characters[seat], InfoRole(seat)))

    def __str__(self) -> str:
        info_player = '\n\t'.join(str(player) for player in self.players)
        return f'[{self.time}]players: \n\t{info_player}'

    def exec(self) -> None:
        self.marks.sort(key=lambda mark: mark.priority)
        while self.marks:
            mark = self.marks.pop()
            mark.exec()

    def vote(
        self, candidates: Sequence[Seat] = [], voters: Sequence[Seat] = []
    ) -> tuple[list[Seat], list[tuple[Seat, Seat]]]:
        ballot = [0] * len(self.players)
        if not candidates:
            candidates = self.alived()
        if not voters:
            voters = self.alived()
        record: list[tuple[Seat, Seat]] = []
        for seat in voters:
            player = self.players[seat]
            vote = player.choose(candidates)
            ballot[vote] += 1
            record.append((player.role.seat, vote))
        highest = max(ballot)
        targets = [
            index for index, value in enumerate(ballot) if value == highest
        ]
        return targets, record

    def boardcast(self, audiences: Sequence[Seat], content: str) -> None:
        log(f'Moderator> {content} > {audiences}')
        for seat in audiences:
            player = self.players[seat]
            player.clues.append(Clue(copy(self.time), None, content))
            if player.character.control == 'input':
                print(f'Moderator> {content}')

    def winner(self) -> Faction:
        count_villagers = 0
        count_werewolfs = 0
        count_god = 0
        alived = self.alived()
        for seat in alived:
            player = self.players[seat]
            match player.role.faction:
                case Faction('villager', 'standard'):
                    count_villagers += 1
                case Faction('werewolf'):
                    count_werewolfs += 1
                case Faction('villager', 'god'):
                    count_god += 1
                case _:
                    raise NotImplementedError('unknown faction')
        if count_villagers + count_werewolfs + count_god == 0:
            return Faction('nobody')
        elif count_villagers + count_god == 0:   # count_villagers * count_god
            return Faction('werewolf')
        elif count_werewolfs == 0:
            return Faction('villager')
        # elif count_villagers + count_god < count_werewolfs:
        #    return Faction('werewolf')
        else:
            return Faction('')

    @functools.cache
    def audience(self) -> list[Seat]:
        return [player.role.seat for player in self.players]

    @functools.cache
    def audience_role(self, role: str) -> list[Seat]:
        return [
            player.role.seat
            for player in self.players
            if player.role.role == role
        ]

    def alived(self) -> list[Seat]:
        return [player.role.seat for player in self.players if player.life]

    def alived_role(self, role: str) -> list[Seat]:
        return [
            player.role.seat
            for player in self.players
            if player.life and player.role.role == role
        ]


game = Game()
log('', clear=True, end='')
log(str(game))
for player in game.players:
    if player.character.control == 'input':
        print(f'You are seat {player.role.seat}, a {player.role.role}.')

# rule
audiences = game.alived()
game.boardcast(
    game.audience(),
    "This game is called The Werewolves of Miller's Hollow. The game setup is 5 villagers, 3 werewolves, and 1 seer. Players list from seat 0 to 8.",
)


while True:
    # dark
    game.time.inc_phase()
    audiences = game.alived()
    game.boardcast(
        game.audience(),
        "It's dark, everyone close your eyes. I will talk with you/your team secretly at night.",
    )

    # werewolf
    game.time.inc_round()
    werewolves = game.alived_role('werewolf')
    game.boardcast(game.audience(), 'Werewolves, please open your eyes!')
    game.boardcast(game.audience(), 'Werewolves, I secretly tell you that ...')
    game.boardcast(
        game.audience_role('werewolf'),
        f'seat {werewolves} are all of the {len(werewolves)} werewolves!',
    )
    game.boardcast(
        game.audience(),
        f'Werewolves, you can choose one player to kill. Who are you going to kill tonight? Choose one from the following living options to kill please: seat {audiences}.',
    )
    targets, record = game.vote(audiences, werewolves)
    target = targets[0]
    mark = game.players[werewolves[0]].mark(target)
    game.marks.append(mark)

    # seer
    game.time.inc_round()
    seers = game.alived_role('seer')
    game.boardcast(game.audience(), 'Seer, please open your eyes!')
    game.boardcast(
        game.audience(),
        f"Seer, you can check one player's identity. Who are you going to verify its identity tonight? Choose one from the following living options please: seat {audiences}.",
    )
    if seers:
        target = game.players[seers[0]].choose(audiences)
        game.boardcast(
            game.audience_role('seer'),
            f'Seat {target} is {game.players[target].role.faction.faction}.',
        )

    # exec
    game.exec()

    # day
    game.time.inc_phase()
    audiences_old = audiences
    audiences = game.alived()
    audiences_died = [
        audience for audience in audiences_old if audience not in audiences
    ]
    summary = (
        f'Seat {audiences_died} are killed last night.'
        if audiences_died
        else 'Nobody died last night.'
    )
    game.boardcast(
        game.audience(),
        f"It's daytime. Everyone woke up. {summary} Seat {audiences} are still alive.",
    )

    # winner
    if game.winner():
        break

    # speech
    game.boardcast(
        game.audience(),
        f'Now freely talk about the current situation based on your observation with a few sentences. E.g. decide whether to reveal your identity.',
    )
    for seat in audiences:
        player = game.players[seat]
        speech = ''
        while not speech:
            try:
                match player.character.control:
                    case 'input':
                        speech = input(f'{seat}> ')
                    case 'ai':
                        speech = get_speech(
                            player.text_clues(),
                            player.role.seat,
                            player.role.role,
                        )
            except Exception as e:
                log(str(e))
        player.boardcast(game.audience(), speech)

    # vote
    game.time.inc_round()
    game.boardcast(
        game.audience(),
        f"It's time to vote. Choose one from the following living options please: seat {audiences}.",
    )
    targets, record = game.vote(audiences, audiences)
    record_text = ', '.join(f'{source}->{target}' for source, target in record)
    if len(targets) == 1:
        game.players[targets[0]].life = False
        game.boardcast(
            game.audience(),
            f'{targets[0]} was eliminated. Vote result: {record_text}.',
        )
    else:
        game.boardcast(
            game.audience(),
            f"It's a tie. Vote result: {record_text}. Choose one from voters with highest votes please: seat {targets}.",
        )
        targets, record = game.vote(targets, audiences)
        record_text = ', '.join(
            f'{source}->{target}' for source, target in record
        )
        if len(targets) == 1:
            game.players[targets[0]].life = False
            game.boardcast(
                game.audience(),
                f'{targets[0]} was eliminated. Vote result: {record_text}.',
            )
        else:
            game.boardcast(
                game.audience(), f"It's a tie. Vote result: {record_text}."
            )

    # winner
    if game.winner():
        break

winner = game.winner()
log(f'{winner} win')
print(f'{winner} win')
log(
    'winners:\n\t'
    + '\n\t'.join(
        str(player)
        for player in game.players
        if winner.eq_faction(player.role.faction)
    )
)

log(str(game))
print(str(game))
