from .header import *

from .ai import output, get_seat, get_speech, get_word
from . import user_data

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
        InfoCharacter(name, 'gui') for name in string.ascii_uppercase
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
        if user_data.user_name:
            random.choice(self.players).character = InfoCharacter(
                user_data.user_name
            )

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
            self.time.inc_round()
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
        for seat in audiences:
            self.players[seat].clues.append(clue)
        log(f'{clue} > {audiences}')
        output(
            [self.players[seat] for seat in audiences],
            clue,
            boardcast=audiences == self.audience(),
        )

    def testament(self, audiences_died: Sequence[Seat]) -> None:
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

    def loop(self) -> bool:
        # dark
        self.time.inc_phase()
        alived_old = self.alived()
        self.boardcast(
            self.audience(),
            "It's dark, everyone close your eyes. I will talk with you/your team secretly at night.",
        )

        # werewolf
        self.time.inc_round()
        werewolves = self.alived_role('werewolf')
        self.boardcast(self.audience(), 'Werewolves, please open your eyes!')
        self.boardcast(
            self.audience(), 'Werewolves, I secretly tell you that ...'
        )
        self.boardcast(
            self.audience_role('werewolf'),
            f'seat {werewolves} are all of the {len(werewolves)} werewolves!',
        )
        self.boardcast(
            self.audience(),
            (
                f'Werewolves, you can choose one player to kill. Who are you going to kill tonight? '
                f'Choose one from the following living options to kill please: seat {alived_old}. '
                '(The player with the highest vote count will be selected. In case of a tie, the one with the smallest seat number will be chosen.)'
            ),
        )
        targets, record = self.vote(alived_old, werewolves)
        target = targets[0]
        mark = self.players[werewolves[0]].mark(target)
        self.marks.append(mark)
        target_for_witch = target

        # witch
        self.time.inc_round()
        witches = self.alived_role('witch')
        self.boardcast(self.audience(), 'Witch, please open your eyes!')
        self.boardcast(self.audience(), f'Witch, I secretly tell you that ...')
        witch_decision = 'pass'
        if witches:
            witch = self.players[witches[0]]
            if not isinstance(witch, Witch):
                raise TypeError('player is not a witch')
            if witch.antidote:
                self.boardcast(
                    witches,
                    f'tonight seat {target_for_witch} has been killed by the werewolves. You have a bottle of antidote, would you like to save him/her? If so, say "save", else, say "pass".',
                )
                word = get_word(witch, ['save', 'pass']).lower()
                match word:
                    case 'save':
                        witch_decision = 'antidote'
                        witch.potion_decision = 'antidote'
                        mark = witch.mark(target_for_witch)
                        self.marks.append(mark)
                    case 'pass':
                        pass
                    case _:
                        raise ValueError('value outsides candidates')
            if witch_decision == 'pass' and witch.poison:
                self.boardcast(
                    witches,
                    f'Witch you decided whether to use the antidote previously. Now you also have a bottle of poison, would you like to use it to kill one of the living players? If so, say "kill", else, say "pass".',
                )
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
                self.boardcast(
                    witches,
                    f'Choose one from the following living options: {alived_old}.',
                )
                seat = get_seat(witch, alived_old)
                mark = witch.mark(seat)
                self.marks.append(mark)

        # seer
        self.time.inc_round()
        seers = self.alived_role('seer')
        self.boardcast(self.audience(), 'Seer, please open your eyes!')
        self.boardcast(
            self.audience(),
            f"Seer, you can check one player's identity. Who are you going to verify its identity tonight? Choose one from the following living options please: seat {alived_old}.",
        )
        if seers:
            target = self.players[seers[0]].choose(alived_old)
            self.boardcast(
                self.audience_role('seer'),
                f'Seat {target} is {self.players[target].role.faction.faction}.',
            )

        # exec
        self.exec()

        # day
        self.time.inc_phase()
        audiences_died = [
            audience
            for audience in alived_old
            if audience not in self.alived()
        ]
        alived_old = self.alived()
        summary = (
            f'Seat {audiences_died} are killed last night.'
            if audiences_died
            else 'Nobody died last night.'
        )
        self.boardcast(
            self.audience(),
            f"It's daytime. Everyone woke up. {summary} Seat {alived_old} are still alive.",
        )

        # verdict
        if self.winner():
            return True
        if self.time.cycle == 1:
            self.boardcast(
                self.audience(),
                f"Since it's the first day, we are able to hear the last words of those who was fatally injured last night.",
            )
            self.testament(audiences_died)
        self.post_exec()
        if self.winner():
            return True
        alived_old = self.alived()

        # speech
        self.boardcast(
            self.audience(),
            f'Now freely talk about the current situation based on your observation with a few sentences. E.g. decide whether to reveal your identity.',
        )
        for seat in alived_old:
            player = self.players[seat]
            speech = get_speech(player)
            player.boardcast(self.audience(), speech)

        # vote
        self.time.inc_round()
        self.boardcast(
            self.audience(),
            f"It's time to vote. Choose one from the following living options please: seat {alived_old}.",
        )
        targets, record = self.vote(alived_old, alived_old)
        record_text = ', '.join(
            f'{source}->{target}' for source, target in record
        )
        if len(targets) == 1:
            self.players[targets[0]].death_causes.append('vote')
            self.players[targets[0]].life = False
            self.boardcast(
                self.audience(),
                f'{targets[0]} was eliminated. Vote result: {record_text}.',
            )
        else:
            self.boardcast(
                self.audience(),
                f"It's a tie. Vote result: {record_text}. Choose one from voters with highest votes please: seat {targets}.",
            )
            targets, record = self.vote(targets, alived_old)
            record_text = ', '.join(
                f'{source}->{target}' for source, target in record
            )
            if len(targets) == 1:
                self.players[targets[0]].death_causes.append('vote')
                self.players[targets[0]].life = False
                self.boardcast(
                    self.audience(),
                    f'{targets[0]} was eliminated. Vote result: {record_text}.',
                )
            else:
                self.boardcast(
                    self.audience(), f"It's a tie. Vote result: {record_text}."
                )

        # verdict
        audiences_died = [
            audience
            for audience in alived_old
            if audience not in self.alived()
        ]
        if self.winner():
            return True
        self.testament(audiences_died)
        self.post_exec()
        if self.winner():
            return True

        return False


game = Game()
log_clear()
log(str(game))
for player in game.players:
    output(
        [player],
        Clue(
            game.time,
            'Moderator',
            f'This line for input.\nYou are seat {player.role.seat}, a {player.role.role}.',
        ),
        clear=True,
    )

# rule
game.boardcast(
    game.audience(),
    "This game is called The Werewolves of Miller's Hollow. The game setup is 3 villagers, 3 werewolves, 1 seer, 1 witch, and 1 hunter. Players list from seat 0 to 8.",
)


while not game.loop():
    pass

winner = game.winner()
end_message = f'{winner} win.\n' 'winners:\n\t' + '\n\t'.join(
    str(player)
    for player in game.players
    if winner.eq_faction(player.role.faction)
) + '\n' + str(game)
log(end_message)
output(game.players, Clue(game.time, 'Moderator', end_message), boardcast=True)
