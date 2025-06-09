from .header import *

from .io import (
    output,
    input_word,
    input_speech,
    input_speech_withdraw,
    input_speech_expose,
    input_speech_withdraw_expose,
)


class BPlayer:
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        self.game = game
        self.char = char
        role = self.__class__.__name__.lower()
        self.role = Role(role, role, role)
        self.life = True
        self.seat = seat
        self.vote = 1.0
        self.night_priority = 0
        self.clues: list[Clue] = []
        self.death_time: Time = Time()
        self.death_causes: list[str] = []

    def __str__(self) -> str:
        life = '☥' if self.life else '†'
        return f'{life}{self.char.name}({self.char.model})[{self.role.kind}]: seat {self.seat}'

    def boardcast(self, pls: Iterable[PPlayer], content: str) -> None:
        self.game.boardcast(pls, content, str(self.seat))

    def unicast(self, pl: PPlayer, content: str) -> None:
        self.game.unicast(pl, content, str(self.seat))

    def receive(self, content: str) -> None:
        self.game.unicast(self, content)

    def day(self) -> None:
        ...

    def night(self) -> None:
        ...

    def speech_expose(self) -> str:
        if user_data.allow_exposure and self.role.faction == 'werewolf':
            speech, expose = input_speech_expose(self)
            if expose == 'expose':
                self.death_time = copy(self.game.time)
                self.death_causes.append('self-exposed')
                self.life = False
                self.game.boardcast(
                    self.game.audience(),
                    f'Seat {self.seat} self-exposed.',
                )
                raise SelfExposureError()
        else:
            speech = input_speech(self)
        return speech

    def speech_withdraw_expose(self) -> tuple[str, str]:
        if user_data.allow_exposure and self.role.faction == 'werewolf':
            speech, withdraw, expose = input_speech_withdraw_expose(self)
            if expose == 'expose':
                self.death_time = copy(self.game.time)
                self.death_causes.append('self-exposed')
                self.life = False
                self.game.boardcast(
                    self.game.audience(),
                    f'Seat {self.seat} self-exposed.',
                )
                raise SelfExposureError()
        else:
            speech, withdraw = input_speech_withdraw(self)
        return speech, withdraw

    def str_mandatory(self, options: Iterable[str]) -> str:
        return input_word(self, options)

    def str_optional(self, options: Iterable[str]) -> str:
        return input_word(self, itertools.chain(options, ('pass',)))

    def pl_mandatory(self, options: Iterable[PPlayer]) -> PPlayer:
        lstr = pls2lstr(options)
        str_ = self.str_mandatory(lstr)
        return seat2pl(self.game, Seat(str_))

    def pl_optional(self, options: Iterable[PPlayer]) -> PPlayer | None:
        lstr = pls2lstr(options)
        str_ = self.str_optional(lstr)
        if str_ == 'pass':
            return None
        return seat2pl(self.game, Seat(str_))


class Villager(BPlayer):
    ...


class Werewolf(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'werewolf'
        self.role.category = 'werewolf'
        self.night_priority = 3

    def night(self) -> None:
        def func(game: PGame, source: PPlayer, target: PPlayer) -> None:
            target.death_time = copy(game.time)
            target.death_causes.append(self.role.kind)
            target.life = False

        if self != self.game.actors[0]:
            return

        self.game.boardcast(
            self.game.actors,
            f'Werewolves {pls2str(self.game.actors)}, please open your eyes! '
            f'Now you can talk secretly with your teammates.',
        )
        for pl in self.game.actors:
            speech = input_speech(pl)
            pl.boardcast(self.game.actors, speech)
        self.game.boardcast(
            self.game.actors,
            f'Werewolves, now you can choose one player to kill.',
        )
        targets = self.game.vote(
            self.game.options, self.game.actors, silent=True
        )
        if not targets:
            self.game.data['target_for_witch'] = None
        elif isinstance(targets, PPlayer):
            self.game.marks.append(
                Mark(self.role.kind, self.game, self, targets, func)
            )
            self.game.data['target_for_witch'] = targets
            self.game.boardcast(
                self.game.actors, f'Werewolves kill seat {targets.seat}.'
            )
        else:
            target = targets[0]
            self.game.marks.append(
                Mark(self.role.kind, self.game, self, target, func)
            )
            self.game.data['target_for_witch'] = target
            self.game.boardcast(
                self.game.actors, f'Werewolves kill seat {target.seat}.'
            )


class Seer(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'
        self.night_priority = 1

    def night(self) -> None:
        self.receive(
            "Seer, please open your eyes! You can check one player's identity."
        )
        pl = self.pl_mandatory(self.game.options)
        self.receive(f'Seat {pl.seat} is {pl.role.faction}.')


class Witch(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'
        self.night_priority = 2

        self.antidote = True
        self.poison = True

    def night(self) -> None:
        def func_a(game: PGame, source: PPlayer, target: PPlayer) -> None:
            assert isinstance(source, self.__class__)
            game.marks = [
                mark
                for mark in game.marks
                if not (mark.target == target and mark.name == 'werewolf')
            ]

        def func_p(game: PGame, source: PPlayer, target: PPlayer) -> None:
            assert isinstance(source, self.__class__)
            target.death_time = copy(game.time)
            target.death_causes.append(self.role.kind)
            target.life = False

        self.receive('Witch, please open your eyes!')
        target: PPlayer | None = self.game.data['target_for_witch']
        if self.antidote:
            target_str = f'seat {target.seat}' if target else 'nobody'
            self.receive(
                f'Tonight {target_str} has been killed by the werewolves.'
            )
        decisions = []
        if self.antidote and target:
            if target != self or self.game.time.cycle == 1:
                decisions.append('save')
        if self.poison:
            decisions.extend(pls2lstr(self.game.options))
        if not decisions:
            return
        self.receive(
            f'You have {int(self.antidote)} antidote and {int(self.poison)} poison. '
            'Say "pass" to pass, say "save" to save, say a seat number to poison a player.'
        )
        str_ = self.str_optional(decisions)
        if str_ == 'pass':
            pass
        elif str_ == 'save':
            self.antidote = False
            assert isinstance(target, PPlayer)
            self.game.marks.append(
                Mark('antidote', self.game, self, target, func_a, priority=1)
            )
        else:
            self.poison = False
            pl = seat2pl(self.game, Seat(str_))
            self.game.marks.append(
                Mark('poison', self.game, self, pl, func_p, priority=1)
            )


class Hunter(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'

    @property
    def life(self) -> bool:
        return self.__life

    @life.setter
    def life(self, value: bool) -> None:
        def func(game: PGame, source: PPlayer, target: PPlayer) -> None:
            game.boardcast(game.audience(), f'Seat {source.seat} is a hunter!')
            source.receive('You can choose a player to shoot.')
            pl = self.pl_optional(game.options)
            if not pl:
                game.boardcast(game.audience(), f"Hunter didn't shoot anyone.")
                return
            pl.death_time = copy(game.time)
            pl.death_causes.append(self.role.kind)
            pl.life = False
            game.boardcast(game.audience(), f'Hunter shot seat {pl.seat}.')

        self.__life = value
        if self.__life:
            return
        if 'witch' in self.death_causes:
            return
        self.game.post_marks.append(
            Mark(self.role.kind, self.game, self, self, func)
        )


class Guard(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'
        self.night_priority = 4

        self.guard: PPlayer | None = None

    def night(self) -> None:
        def func(game: PGame, source: PPlayer, target: PPlayer) -> None:
            assert isinstance(source, self.__class__)
            if any(
                mark.target == target and mark.name == 'antidote'
                for mark in game.marks
            ):
                game.marks = [
                    mark
                    for mark in game.marks
                    if not (mark.target == target and mark.name == 'antidote')
                ]
                return
            game.marks = [
                mark
                for mark in game.marks
                if not (mark.target == target and mark.name == 'werewolf')
            ]

        self.receive(
            'Guard, please open your eyes! Who will you protect tonight?'
        )
        options = [pl for pl in self.game.options if pl != self.guard]
        pl = self.pl_optional(options)
        self.guard = pl
        if pl:
            self.game.marks.append(
                Mark(self.role.kind, self.game, self, pl, func, priority=2)
            )


class Fool(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'

        self.exposed = False

    @property
    def life(self) -> bool:
        return self.__life

    @life.setter
    def life(self, value: bool) -> None:
        def func(game: PGame, source: PPlayer, target: PPlayer) -> None:
            game.boardcast(game.audience(), f'Seat {source.seat} is a fool!')

        self.__life = value
        if self.__life:
            return
        if 'witch' in self.death_causes:
            return
        if 'vote' not in self.death_causes:
            return
        if self.exposed:
            return
        self.exposed = True
        self.life = True
        self.vote = 0.0
        self.death_time = Time()
        self.death_causes.clear()
        self.game.post_marks.append(
            Mark(self.role.kind, self.game, self, self, func)
        )


class Badge:
    def __init__(self, game: PGame) -> None:
        self.owner: PPlayer | None = None
        self.game = game

    def election(self) -> None:
        candidates: list[PPlayer] = []
        quitters: list[PPlayer] = []
        self.game.boardcast(
            self.game.options,
            'Will you participate in the sheriff election (yes/no)?',
        )
        for pl in self.game.options:
            option = pl.str_mandatory(('yes', 'no'))
            if option == 'yes':
                candidates.append(pl)
        voters = [pl for pl in self.game.options if pl not in candidates]
        if not candidates:
            self.game.boardcast(
                self.game.audience(),
                'No one is running for sheriff.',
            )
            return
        if not voters:
            self.game.boardcast(
                self.game.audience(),
                'Everyone is running for sheriff.',
            )
            return
        self.game.boardcast(
            self.game.audience(),
            f'Sheriff candidates are seat {pls2str(candidates)}. Give a campaign speech for the sheriff election.',
        )
        for pl in candidates:
            speech, withdraw = pl.speech_withdraw_expose()
            if withdraw == 'withdraw':
                self.game.boardcast(
                    self.game.audience(),
                    f'Seat {pl.seat} quit the election.',
                )
                quitters.append(pl)
                continue
            pl.boardcast(self.game.audience(), speech)
        candidates = [pl for pl in candidates if pl not in quitters]
        if not candidates:
            self.game.boardcast(
                self.game.audience(),
                'No one is running for sheriff.',
            )
            return
        self.game.boardcast(
            self.game.audience(),
            f'Sheriff candidates are seat {pls2str(candidates)}. Now, please vote to elect the sheriff.',
        )
        targets = self.game.vote(candidates, voters)
        if not targets:
            pass
        elif isinstance(targets, PPlayer):
            self.owner = targets
            targets.vote = 1.5
            user_data.election_round = 0
        else:
            self.game.time.inc_round()
            self.game.boardcast(
                targets, 'Give the additional campaign speech.'
            )
            targets.reverse()
            for pl in targets:
                speech = pl.speech_expose()
                pl.boardcast(self.game.audience(), speech)
            self.game.boardcast(self.game.audience(), 'Please vote again.')
            targets = self.game.vote(targets, voters)
            if not targets:
                pass
            elif isinstance(targets, PPlayer):
                self.owner = targets
                targets.vote = 1.5
                user_data.election_round = 0
            else:
                pass

    def badge(self) -> None:
        if not self.owner:
            return
        if self.owner.life == False:
            self.owner.receive(
                "Please transfer the sheriff's badge. If passed, then destroy the badge."
            )
            target = self.owner.pl_optional(self.game.options)
            if not target:
                self.owner = None
                self.game.boardcast(
                    self.game.audience(), 'The badge was destroyed.'
                )
                return
            self.owner = target
            target.vote = 1.5
            self.game.boardcast(
                self.game.audience(),
                f'The badge was passed to seat {target.seat}.',
            )

    def speakers(self) -> list[PPlayer]:
        self.badge()
        if not self.owner:
            return self.game.options

        speakers = copy(self.game.options)
        if len(self.game.died) == 1:
            reference = self.game.died[0]
            self.owner.receive(
                'Choose the left/right side of the deceased as the first speaker (left/right).'
            )
        else:
            reference = self.owner
            self.owner.receive(
                'Choose your left/right side as the first speaker (left/right).'
            )
        option = self.owner.str_mandatory(('left', 'right'))
        if option == 'left':
            speakers.reverse()
            if speakers[-1].seat < reference.seat:
                while speakers[0].seat >= reference.seat:
                    speakers.append(speakers.pop(0))
        elif option == 'right':
            if speakers[-1].seat > reference.seat:
                while speakers[0].seat <= reference.seat:
                    speakers.append(speakers.pop(0))

        return speakers


class Game:
    def __init__(
        self, chars: Iterable[Char], roles: Iterable[type[PPlayer]]
    ) -> None:
        self.chars = list(chars)
        self.roles = list(roles)
        self.time = Time()
        self.players: list[PPlayer] = []
        self.marks: list[Mark] = []
        self.post_marks: list[Mark] = []
        self.badge: PBadge = Badge(self)
        self.options: list[PPlayer] = []
        self.actors: list[PPlayer] = []
        self.died: list[PPlayer] = []
        self.data: dict[str, Any] = {}

        roles = Counter(self.roles)
        self.data['roles'] = ', '.join(
            f'{num} {Pl.__name__.lower()}' for Pl, num in roles.items()
        )

        users = len(user_data.user_names)
        ai = len(self.roles) - users
        if ai < 0:
            raise ValueError('too many users')
        chars = random.sample(self.chars, ai)
        random.shuffle(user_data.models)
        for char in chars:
            char.model = user_data.models.pop()
        for user_name in user_data.user_names:
            chars.append(Char(user_name, 'file'))
        random.shuffle(chars)
        random.shuffle(self.roles)
        for seat, Pl in enumerate(self.roles):
            self.players.append(Pl(self, chars[seat], Seat(seat)))

    def __str__(self) -> str:
        info_player = '\n\t'.join(str(pl) for pl in self.players)
        return f'[{self.time}]players: \n\t{info_player}'

    def boardcast(
        self,
        pls_iter: Iterable[PPlayer],
        content: str,
        source: str = 'Moderator',
    ) -> None:
        pls = list(pls_iter)
        clue = Clue(copy(self.time), source, content)
        for pl in pls:
            pl.clues.append(clue)
        output(pls, clue)

    def unicast(
        self, pl: PPlayer, content: str, source: str = 'Moderator'
    ) -> None:
        self.boardcast((pl,), content, source)

    def loop(self) -> None:
        start_message = f"players: \n\t{'\n\t'.join(f'{pl.char.name}(seat {pl.seat})' for pl in self.players)}"
        output(
            self.audience(),
            Clue(self.time, 'Moderator', f'{start_message}\n'),
            system=True,
            clear_text=f'Please wait...\nThe upper line for input.\n',
        )
        for pl in self.players:
            self.unicast(
                pl,
                f'You are seat {pl.seat}, a {pl.role.kind}.',
            )

        self.options = list(self.alived())
        self.boardcast(
            self.audience(),
            "This game is called The Werewolves of Miller's Hollow. "
            f"The game setup is {self.data['roles']}. "
            f'Players list from seat 1 to {len(self.options)}.',
        )

        while True:
            self.time.inc_phase()
            self.night()
            if self.exec():
                break
            if self.post_exec():
                break
            try:
                self.time.inc_phase()
                self.day()
            except SelfExposureError as e:
                pass
            if self.exec():
                break
            if self.post_exec():
                break

        winner = self.winner()
        end_message = f'{winner.faction} win.\n' 'winners:\n\t' + '\n\t'.join(
            str(pl) for pl in self.players if winner.eq_faction(pl.role)
        ) + '\n' + str(self)
        output(
            self.audience(),
            Clue(self.time, 'Moderator', end_message),
            system=True,
        )

    def day(self) -> None:
        self.died = [
            pl
            for pl in self.audience()
            if pl.death_time.cycle == self.time.cycle - 1
            and pl.death_time.phase == Phase.NIGHT
        ]
        summary = (
            f'Seat {pls2str(self.died)} are killed last night. '
            if self.died
            else 'Nobody died last night. '
        )
        self.boardcast(
            self.audience(),
            f"It's daytime. Everyone woke up. {summary}Seat {pls2str(self.options)} are still alive.",
        )

        # day 2
        if self.time.cycle == 2:
            self.testament(self.died)

        # sheriff
        if user_data.election_round:
            user_data.election_round -= 1
            self.badge.election()
        speakers = self.badge.speakers()

        # speech
        self.boardcast(
            self.audience(),
            f'Now freely talk about the current situation based on your observation with a few sentences.',
        )
        for pl in speakers:
            speech = pl.speech_expose()
            pl.boardcast(self.audience(), speech)

        # vote
        self.time.inc_round()
        self.boardcast(self.audience(), "It's time to vote.")
        targets = self.vote(self.options, self.options)
        if not targets:
            pass
        elif isinstance(targets, PPlayer):
            targets.death_time = copy(self.time)
            targets.death_causes.append('vote')
            targets.life = False
            self.badge.badge()
            self.testament((targets,))
        else:
            self.time.inc_round()
            self.boardcast(targets, 'Give the additional speech.')
            targets.reverse()
            for pl in targets:
                speech = pl.speech_expose()
                pl.boardcast(self.audience(), speech)
            self.boardcast(self.audience(), 'Please vote again.')
            targets = self.vote(targets, self.options)
            if not targets:
                pass
            elif isinstance(targets, PPlayer):
                targets.death_time = copy(self.time)
                targets.death_causes.append('vote')
                targets.life = False
                self.badge.badge()
                self.testament((targets,))
            else:
                pass

    def night(self) -> None:
        self.boardcast(
            self.audience(),
            "It's dark, everyone close your eyes. I will talk with you/your team secretly at night.",
        )

        actions: dict[int, list[PPlayer]] = {}
        for pl in self.players:
            if not pl.life:
                continue
            actions.setdefault(pl.night_priority, []).append(pl)
        while actions:
            self.time.inc_round()
            self.actors = actions.pop(max(actions))
            for pl in self.actors:
                pl.night()

    def exec(self) -> bool:
        self.marks.sort(key=lambda mark: mark.priority)
        while self.marks:
            mark = self.marks.pop()
            mark.exec()
        self.options = list(self.alived())
        if self.winner():
            return True
        return False

    def post_exec(self) -> bool:
        while self.post_marks:
            self.time.inc_round()
            self.post_marks.sort(key=lambda mark: mark.priority)
            mark = self.post_marks.pop()
            mark.exec()
            self.options = list(self.alived())
            if self.winner():
                return True
        return False

    def winner(self) -> Role:
        count_villagers = 0
        count_god = 0
        count_werewolfs = 0
        for pl in self.options:
            match pl.role:
                case Role('villager', 'villager'):
                    count_villagers += 1
                case Role('villager', 'god'):
                    count_god += 1
                case Role('werewolf'):
                    count_werewolfs += 1
                case _:
                    raise NotImplementedError('unknown faction')
        if count_villagers + count_werewolfs + count_god == 0:
            return Role('nobody')
        if count_werewolfs == 0:
            return Role('villager')
        if user_data.win_condition == 'all':
            if count_villagers + count_god == 0:
                return Role('werewolf')
        elif user_data.win_condition == 'partial':
            if count_villagers * count_god == 0:
                return Role('werewolf')
        # if count_villagers + count_god < count_werewolfs:
        #    return Role('werewolf')
        return Role('')

    def vote(
        self,
        candidates_iter: Iterable[PPlayer],
        voters_iter: Iterable[PPlayer],
        silent: bool = False,
    ) -> None | PPlayer | list[PPlayer]:
        candidates = list(candidates_iter)
        voters = list(voters_iter)
        ballot = {pl: 0.0 for pl in candidates}
        abstain = 0
        vote_text = ''
        for pl in voters:
            vote = pl.pl_optional(candidates)
            sign = ''
            if pl.vote == 1.5:
                sign = '*'
            elif pl.vote == 0.0:
                sign = '†'
            if not vote:
                abstain += 1
                vote_text += f'{pl.seat}{sign}->pass, '
            else:
                ballot[vote] += pl.vote
                vote_text += f'{pl.seat}{sign}->{vote.seat}, '
        if abstain == len(voters):
            if not silent:
                self.boardcast(self.audience(), 'Everyone passed.')
            return None
        highest = max(ballot.values())
        targets = [pl for pl, value in ballot.items() if value == highest]
        if len(targets) == 1:
            target = targets[0]
            if not silent:
                self.boardcast(
                    self.audience(),
                    f'Seat {target.seat} got the highest votes. Vote result: {vote_text[:-2]}.',
                )
            return target
        else:
            if not silent:
                self.boardcast(
                    self.audience(),
                    f"It's a tie. Vote result: {vote_text[:-2]}.",
                )
            return targets

    def testament(self, died: Iterable[PPlayer]) -> None:
        self.time.inc_round()
        for pl in died:
            pl.receive('You are dying, any last words?')
            speech = input_speech(pl)
            pl.boardcast(self.audience(), speech)

    def audience(self) -> Generator[PPlayer]:
        return (pl for pl in self.players)

    def audience_role(self, role: str) -> Generator[PPlayer]:
        return (pl for pl in self.players if pl.role.kind == role)

    def alived(self) -> Generator[PPlayer]:
        return (pl for pl in self.players if pl.life)

    def alived_role(self, role: str) -> Generator[PPlayer]:
        return (pl for pl in self.players if pl.life and pl.role.kind == role)
