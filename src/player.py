from .header import *

from .ai.ai import get_seat, get_speech, get_word


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
        self.death_causes: list[str] = []

    def __str__(self) -> str:
        life = '☥' if self.life else '†'
        return f'{life}{self.character.name}(seat {self.role.seat})[{self.role.role}]'

    def mark(self, target: Seat) -> Mark:
        raise NotImplementedError('mark not implemented')

    def choose(self, candidates: Sequence[Seat]) -> Seat:
        return get_seat(self, candidates)

    def boardcast(self, audiences: Sequence[Seat], content: str) -> None:
        game.boardcast(audiences, content, str(self.role.seat))

    def text_clues(self) -> str:
        dialogues = '\n'.join(str(clue) for clue in self.clues)
        return f'Dialogues:\n{dialogues}'


class Villager(BPlayer):
    ...


class Werewolf(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction.faction = 'werewolf'
        super().__init__(character, role)

    def mark(self, target: Seat) -> Mark:
        def func(source: Seat, target: Seat) -> None:
            game.players[target].death_causes.append('werewolf')
            game.players[target].life = False

        return Mark(self.role.role, self.role.seat, target, func)


class Seer(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction.category = 'god'
        super().__init__(character, role)


class Witch(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction.category = 'god'
        super().__init__(character, role)

        self.antidote = True
        self.poison = True
        self.potion_decision = 'pass'

    def mark(self, target: Seat) -> Mark:
        def func(source: Seat, target: Seat) -> None:
            source_player = game.players[source]
            target_player = game.players[target]
            if not isinstance(source_player, Witch):
                raise TypeError('player is not a witch')
            match source_player.potion_decision:
                case 'antidote':
                    source_player.antidote = False
                    game.marks = [
                        mark
                        for mark in game.marks
                        if not (
                            mark.target == target
                            and mark.name == Werewolf.__name__.lower()
                        )
                    ]
                case 'poison':
                    source_player.poison = False
                    target_player.death_causes.append('witch')
                    target_player.life = False
                case _:
                    raise ValueError('unknown potion decision')

        return Mark(self.role.role, self.role.seat, target, func, priority=1)


class Hunter(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        role.faction.category = 'god'
        super().__init__(character, role)

    def mark(self, target: Seat) -> Mark:
        def func(source: Seat, target: Seat) -> None:
            game.boardcast(
                game.audience(), f'Seat {self.role.seat} is a hunter!'
            )
            game.boardcast(
                [self.role.seat],
                f'Please choose a living player to shoot: {game.alived()}.',
            )
            seat = get_seat(self, game.alived())

            game.players[seat].death_causes.append('hunter')
            game.players[seat].life = False
            game.boardcast(
                game.audience(), f'Seat {source} shoot seat {seat}.'
            )

        return Mark(self.role.role, self.role.seat, target, func, priority=1)

    @property
    def life(self) -> bool:
        return self.__life

    @life.setter
    def life(self, value: bool) -> None:
        self.__life = value
        if self.__life:
            return
        if 'witch' in self.death_causes:
            return
        game.post_marks.append(self.mark(self.role.seat))


class Game:
    characters = [
        InfoCharacter('A'),
        InfoCharacter('B'),
        InfoCharacter('C'),
        InfoCharacter('D'),
        InfoCharacter('E'),
        InfoCharacter('F'),
        InfoCharacter('G'),
        InfoCharacter('H'),
        InfoCharacter('I'),
    ]

    roles: list[type[PPlayer]] = [
        Villager,
        Villager,
        Villager,
        Werewolf,
        Werewolf,
        Werewolf,
        Seer,
        Witch,
        Hunter,
    ]

    def __init__(self) -> None:
        self.time = Time()
        self.players: list[PPlayer] = []
        self.marks: list[Mark] = []
        self.post_marks: list[Mark] = []

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

    def post_exec(self) -> None:
        while self.post_marks:
            self.post_marks.sort(key=lambda mark: mark.priority)
            mark = self.post_marks.pop()
            mark.exec()
            if game.winner():
                break

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

    def boardcast(
        self,
        audiences: Sequence[Seat],
        content: str,
        source: str = 'Moderator',
    ) -> None:
        clue = Clue(copy(self.time), source, content)
        log(f'{clue} > {audiences}')
        for seat in audiences:
            player = self.players[seat]
            player.clues.append(clue)
            if player.character.control == 'input':
                print(str(clue))

    def testament(self) -> None:
        for seat in audiences_died:
            player = game.players[seat]
            if (
                'witch' in player.death_causes
                or 'hunter' in player.death_causes
            ):
                continue
            game.boardcast(
                [seat], 'You are dying, any last words (a few sentences)?'
            )
            speech = get_speech(player)
            player.boardcast(game.audience(), speech)

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
    "This game is called The Werewolves of Miller's Hollow. The game setup is 3 villagers, 3 werewolves, 1 seer, 1 witch, and 1 hunter. Players list from seat 0 to 8.",
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
        (
            f'Werewolves, you can choose one player to kill. Who are you going to kill tonight? '
            f'Choose one from the following living options to kill please: seat {audiences}. '
            '(The player with the highest vote count will be selected. In case of a tie, the one with the smallest seat number will be chosen.)'
        ),
    )
    targets, record = game.vote(audiences, werewolves)
    target = targets[0]
    mark = game.players[werewolves[0]].mark(target)
    game.marks.append(mark)
    target_for_witch = target

    # witch
    game.time.inc_round()
    witches = game.alived_role('witch')
    game.boardcast(game.audience(), 'Witch, please open your eyes!')
    game.boardcast(game.audience(), f'Witch, I secretly tell you that ...')
    game.boardcast(
        witches,
        f'tonight seat {target_for_witch} has been killed by the werewolves.',
    )
    game.boardcast(
        game.audience(),
        f'You have a bottle of antidote, would you like to save him/her? If so, say "save", else, say "pass".',
    )
    witch_decision = 'pass'
    if witches:
        witch = game.players[witches[0]]
        if not isinstance(witch, Witch):
            raise TypeError('player is not a witch')
        if witch.antidote:
            word = get_word(witch, ['save', 'pass']).lower()
            match word:
                case 'save':
                    witch_decision = 'antidote'
                    witch.potion_decision = 'antidote'
                    mark = witch.mark(target_for_witch)
                    game.marks.append(mark)
                case 'pass':
                    pass
                case _:
                    raise ValueError('value outsides candidates')
    game.boardcast(
        game.audience(),
        f'Witch you decided whether to use the antidote previously. Now you also have a bottle of poison, would you like to use it to kill one of the living players? If so, say "kill", else, say "pass".',
    )
    if witches:
        witch = game.players[witches[0]]
        if not isinstance(witch, Witch):
            raise TypeError('player is not a witch')
        if witch_decision == 'pass' and witch.poison:
            word = get_word(witch, ['kill', 'pass']).lower()
            match word:
                case 'kill':
                    witch_decision = 'poison'
                    witch.potion_decision = 'poison'
                case 'pass':
                    pass
                case _:
                    raise ValueError('value outsides candidates')
        if witch_decision == 'poison':
            game.boardcast(
                witches,
                f'Choose one from the following living options: {audiences}.',
            )
            seat = get_seat(witch, audiences)
            mark = witch.mark(seat)
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

    # verdict
    if game.winner():
        break
    if game.time.cycle == 1:
        game.boardcast(
            game.audience(),
            f"Since it's the first day, we are able to hear the last words of those who was fatally injured last night.",
        )
        game.testament()
    game.post_exec()

    # speech
    game.boardcast(
        game.audience(),
        f'Now freely talk about the current situation based on your observation with a few sentences. E.g. decide whether to reveal your identity.',
    )
    for seat in audiences:
        player = game.players[seat]
        speech = get_speech(player)
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
        game.players[targets[0]].death_causes.append('vote')
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
            game.players[targets[0]].death_causes.append('vote')
            game.players[targets[0]].life = False
            game.boardcast(
                game.audience(),
                f'{targets[0]} was eliminated. Vote result: {record_text}.',
            )
        else:
            game.boardcast(
                game.audience(), f"It's a tie. Vote result: {record_text}."
            )

    # verdict
    if game.winner():
        break
    game.testament()
    game.post_exec()

winner = game.winner()
end_message = f'{winner} win.\n' 'winners:\n\t' + '\n\t'.join(
    str(player)
    for player in game.players
    if winner.eq_faction(player.role.faction)
) + '\n' + str(game)
print(end_message)
log(end_message)
