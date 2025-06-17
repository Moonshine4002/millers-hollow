from .header import *

from .io import Input, Output, output_info, get_inputs, async_get_inputs


class BPlayer:
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        self.game = game
        self.char = char
        role = self.__class__.__name__.lower()
        self.role = Role(role, role, role)
        self.life = True
        self.seat = seat
        self.night_priority = 0
        self.vote = 1.0
        self.can_expose = False
        self.death: list[Info] = []
        self.tasks: list[Input] = []
        self.results: list[Output] = []

    def __str__(self) -> str:
        life = '☥' if self.life else '†'
        return f'{self.seat}{life} {self.role.kind} {self.char.name}({self.char.model}): {self.char.description}'

    def str_public(self) -> str:
        return f'{self.seat} {self.char.name}({self.char.model}): {self.char.description}'

    def boardcast(self, pls: Iterable[PPlayer], content: str) -> None:
        info = Info(copy(self.game.time), (self,), tuple(pls), content)
        self.game.info.append(info)
        output_info(info)

    def receive(self, content: str) -> None:
        self.game.unicast(self, content)

    def day(self) -> None:
        ...

    def night(self) -> None:
        ...

    def expose(self) -> None:
        self.death.append(
            Info(copy(self.game.time), (self,), (self,), 'self-exposed')
        )
        self.life = False
        self.game.boardcast(
            self.game.audience(),
            f'Seat {self.seat} (a {self.role.faction}) self-exposed!',
        )
        raise SelfExposureError()


def input_word(pl: PPlayer, prompt: str, option: Iterable[str]) -> str:
    pl.tasks = [Input(prompt, tuple(option))]
    get_inputs(pl)
    (choice,) = pl.results
    return choice.output


def input_op(
    pl: PPlayer,
    prompt: str,
    op1: Iterable[PPlayer] = [],
    op2: Iterable[str] = [],
) -> str:
    lstr = LStr(pls2seats(op1))
    lstr.extend(LStr(op2))
    return input_word(pl, prompt, lstr)


async def async_input_words(
    pls_iter: Iterable[PPlayer], prompt: str, option: Iterable[str]
) -> Iterable[str]:
    pls = list(pls_iter)
    for pl in pls:
        pl.tasks = [Input(prompt, tuple(option))]
    await asyncio.gather(*(async_get_inputs(pl) for pl in pls))
    return (pl.results[0].output for pl in pls)


def async_input_op(
    pls: Iterable[PPlayer],
    prompt: str,
    op1: Iterable[PPlayer] = [],
    op2: Iterable[str] = [],
) -> Iterable[str]:
    lstr = LStr(pls2seats(op1))
    lstr.extend(LStr(op2))
    return asyncio.run(async_input_words(pls, prompt, lstr))


def input_speech(pl: PPlayer, prompt: str) -> str:
    pl.tasks = [Input(prompt)]
    get_inputs(pl)
    (speech,) = pl.results
    return speech.output


def input_speech_quit(pl: PPlayer, prompt: str) -> tuple[str, str]:
    pl.tasks = [
        Input(prompt),
        Input('Will you quit the election?', ('quit', 'no')),
    ]
    get_inputs(pl)
    speech, quit = pl.results
    return speech.output, quit.output


def input_speech_expose(pl: PPlayer, prompt: str) -> tuple[str, str]:
    pl.tasks = [
        Input(prompt),
        Input('Will you make a self-exposure?', ('expose', 'no')),
    ]
    get_inputs(pl)
    speech, expose = pl.results
    return speech.output, expose.output


def input_speech_quit_expose(pl: PPlayer, prompt: str) -> tuple[str, str, str]:
    pl.tasks = [
        Input(prompt),
        Input('Will you quit the election?', ('quit', 'no')),
        Input('Will you make a self-exposure?', ('expose', 'no')),
    ]
    get_inputs(pl)
    speech, quit, expose = pl.results
    return speech.output, quit.output, expose.output


def speech_expose(pl: PPlayer, prompt: str) -> str:
    if pl.can_expose:
        speech, expose = input_speech_expose(pl, prompt)
        if expose == 'expose':
            pl.expose()
        return speech
    else:
        return input_speech(pl, prompt)


def speech_quit_expose(pl: PPlayer, prompt: str) -> tuple[str, str]:
    if pl.can_expose:
        speech, quit, expose = input_speech_quit_expose(pl, prompt)
        if expose == 'expose':
            pl.expose()
        return speech, quit
    else:
        return input_speech_quit(pl, prompt)


class Villager(BPlayer):
    ...


class Werewolf(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'werewolf'
        self.role.category = 'werewolf'
        self.night_priority = 3
        if user_data.allow_exposure:
            self.can_expose = True

    def night(self) -> None:
        def func(game: PGame, source: PPlayer, target: PPlayer) -> None:
            target.death.append(
                Info(copy(game.time), (source,), (target,), self.role.faction)
            )
            target.life = False

        if self != self.game.actors[0]:
            return

        self.game.boardcast(
            self.game.actors,
            f'Werewolves {pls2str(self.game.actors)}, please open your eyes!',
        )
        for pl in self.game.actors:
            if len(self.game.actors) == 1:
                break
            speech = input_speech(pl, 'talk with your teammates')
            pl.boardcast(self.game.actors, speech)
        targets = self.game.vote(
            self.game.options,
            self.game.actors,
            'choose one player to kill',
            silent=True,
        )
        if not targets:
            self.game.data['target_for_witch'] = None
            self.game.boardcast(self.game.actors, 'Werewolves kill nobody.')
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


class WhiteWolf(Werewolf):
    def expose(self) -> None:
        self.death.append(
            Info(copy(self.game.time), (self,), (self,), 'self-exposed')
        )
        self.life = False
        self.game.boardcast(
            self.game.audience(),
            f'Seat {self.seat} (a {self.role.faction}) self-exposed!',
        )
        choice = input_op(
            self,
            'pass or choose a player to kill',
            self.game.options,
            ('pass',),
        )
        if choice == 'pass':
            return
        self.game.boardcast(
            self.game.audience(), f'Seat {self.seat} is a {self.role.kind}!'
        )
        pl = str2pl(self.game, choice)
        self.game.boardcast(
            self.game.audience(),
            f'Seat {self.seat} killed seat {pl.seat}.',
        )
        pl.death.append(
            Info(copy(self.game.time), (self,), (pl,), self.role.kind)
        )
        pl.life = False
        raise SelfExposureError()


class BlackWolf(Werewolf):
    @property
    def life(self) -> bool:
        return self.__life

    @life.setter
    def life(self, value: bool) -> None:
        def func(game: PGame, source: PPlayer, target: PPlayer) -> None:
            choice = input_op(
                source,
                'pass or choose a player to kill',
                game.options,
                ('pass',),
            )
            if choice == 'pass':
                return
            game.boardcast(
                game.audience(), f'Seat {source.seat} is a {self.role.kind}!'
            )
            pl = str2pl(game, choice)
            game.boardcast(
                game.audience(),
                f'Seat {self.seat} kill seat {pl.seat}.',
            )
            pl.death.append(
                Info(copy(game.time), (source,), (pl,), self.role.kind)
            )
            pl.life = False

        self.__life = value
        if self.__life:
            return
        if any('witch' == death.content for death in self.death):
            return
        self.game.post_marks.append(
            Mark(self.role.kind, self.game, self, self, func)
        )


class Seer(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'
        self.night_priority = 1

    def night(self) -> None:
        self.game.boardcast(self.game.actors, 'Seer, please open your eyes!')
        choice = input_op(
            self, "check one player's identity", self.game.options
        )
        pl = str2pl(self.game, choice)
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
            game.marks = [
                mark
                for mark in game.marks
                if not (mark.target == target and mark.name == 'werewolf')
            ]

        def func_p(game: PGame, source: PPlayer, target: PPlayer) -> None:
            target.death.append(
                Info(copy(game.time), (source,), (target,), self.role.kind)
            )
            target.life = False

        self.receive('Witch, please open your eyes!')
        target: PPlayer | None = self.game.data['target_for_witch']
        if self.antidote:
            target_str = f'seat {target.seat}' if target else 'nobody'
            self.receive(
                f'Tonight {target_str} has been killed by the werewolves.'
            )
        self.game.boardcast(
            self.game.actors,
            f'You have {int(self.antidote)} antidote and {int(self.poison)} poison.',
        )
        antidote = (
            self.antidote
            and target
            and not (target == self and self.game.time.cycle != 1)
        )
        poison = self.poison
        if antidote and poison:
            choice = input_op(
                self,
                'pass, save, or choose a seat number to poison',
                self.game.options,
                ('save', 'pass'),
            )
        elif antidote:
            choice = input_op(self, 'pass or save', op2=('save', 'pass'))
        elif poison:
            choice = input_op(
                self,
                'pass or choose a seat number to poison',
                self.game.options,
                ('pass',),
            )
        else:
            return
        if choice == 'pass':
            return
        elif choice == 'save':
            self.antidote = False
            assert isinstance(target, PPlayer)
            self.game.marks.append(
                Mark('antidote', self.game, self, target, func_a, priority=1)
            )
        else:
            self.poison = False
            pl = str2pl(self.game, choice)
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
            game.boardcast(
                game.audience(), f'Seat {source.seat} is a {self.role.kind}!'
            )
            choice = input_op(
                source,
                'pass or choose a player to shoot',
                game.options,
                ('pass',),
            )
            if choice == 'pass':
                game.boardcast(
                    game.audience(),
                    f"Seat {self.seat} didn't shoot anyone.",
                )
                return
            pl = str2pl(game, choice)
            game.boardcast(
                game.audience(),
                f'Seat {self.seat} shot seat {pl.seat}.',
            )
            pl.death.append(
                Info(copy(game.time), (source,), (pl,), self.role.kind)
            )
            pl.life = False

        self.__life = value
        if self.__life:
            return
        if any('witch' == death.content for death in self.death):
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

        self.game.boardcast(self.game.actors, 'Guard, please open your eyes!')
        choice = input_op(
            self, 'who will you protect tonight?', self.game.options, ('pass',)
        )
        if choice == 'pass':
            self.guard = None
            return
        pl = str2pl(self.game, choice)
        self.guard = pl
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
            game.boardcast(
                game.audience(), f'Seat {source.seat} is a {self.role.kind}!'
            )

        self.__life = value
        if self.__life:
            return
        if any('vote' != death.content for death in self.death):
            return
        if self.exposed:
            return
        self.exposed = True
        self.life = True
        self.vote = 0.0
        self.death.clear()
        self.game.post_marks.append(
            Mark(self.role.kind, self.game, self, self, func)
        )


class Knight(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'
        self.can_expose = True

    def expose(self) -> None:
        self.game.boardcast(
            self.game.audience(),
            f'Seat {self.seat} (a {self.role.kind}) self-exposed!',
        )
        choice = input_op(
            self,
            'choose a player to duel',
            self.game.options,
        )
        pl = str2pl(self.game, choice)
        self.game.boardcast(
            self.game.audience(),
            f'Seat {self.seat} duel with seat {pl.seat}. Seat {pl.seat} is a {pl.role.faction}!',
        )
        if pl.role.faction == 'werewolf':
            pl.death.append(
                Info(copy(self.game.time), (self,), (pl,), self.role.kind)
            )
            pl.life = False
            raise SelfExposureError()
        else:
            self.death.append(
                Info(copy(self.game.time), (self,), (self,), self.role.kind)
            )
            self.life = False


class Badge:
    def __init__(self, game: PGame) -> None:
        self.owner: PPlayer | None = None
        self.game = game

    def election(self) -> None:
        candidates: list[PPlayer] = []
        quitters: list[PPlayer] = []
        choices = async_input_op(
            self.game.options,
            'Will you participate in the sheriff election?',
            op2=('yes', 'no'),
        )

        for pl, choice in zip(self.game.options, choices):
            if choice == 'yes':
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
            f'Sheriff candidates are seat {pls2str(candidates)}.',
        )
        for pl in candidates:
            speech, quit = speech_quit_expose(
                pl, 'Give a campaign speech for the sheriff election.'
            )
            if quit == 'quit':
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
            f'Sheriff candidates are seat {pls2str(candidates)}.',
        )
        targets = self.game.vote(
            candidates,
            voters,
            'your vote to elect the sheriff',
        )
        if not targets:
            pass
        elif isinstance(targets, PPlayer):
            self.owner = targets
            targets.vote = 1.5
            user_data.election_round = 0
        else:
            self.game.time.inc_stage()
            targets.reverse()
            for pl in targets:
                speech = speech_expose(
                    pl, 'Give the additional campaign speech.'
                )
                pl.boardcast(self.game.audience(), speech)
            targets = self.game.vote(
                targets, voters, 'vote again to elect the sheriff'
            )
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
            self.game.boardcast(
                self.game.audience(),
                'The former sheriff is passing the badge.',
            )
            choice = input_op(
                self.owner,
                'Say "destroy" to destroy the badge or say a seat number to transfer the badge.',
                self.game.options,
                ['destroy'],
            )
            if choice == 'destroy':
                self.owner = None
                self.game.boardcast(
                    self.game.audience(), 'The badge was destroyed.'
                )
                return
            pl = str2pl(self.game, choice)
            self.owner = pl
            pl.vote = 1.5
            self.game.boardcast(
                self.game.audience(),
                f'The badge was passed to seat {pl.seat}.',
            )

    def speakers(self) -> list[PPlayer]:
        if not self.owner:
            return self.game.options

        speakers = copy(self.game.options)
        if len(self.game.died) == 1:
            reference = self.game.died[0]
            choice = input_op(
                self.owner,
                f'Choose the left/right side of seat {reference.seat} as the first speaker.',
                op2=('left', 'right'),
            )
        else:
            reference = self.owner
            choice = input_op(
                self.owner,
                'Choose your left/right side as the first speaker.',
                op2=('left', 'right'),
            )
        if choice == 'left':
            speakers.reverse()
            if speakers[-1].seat < reference.seat:
                while speakers[0].seat >= reference.seat:
                    speakers.append(speakers.pop(0))
        elif choice == 'right':
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
        self.info: list[Info] = []
        self.badge: PBadge = Badge(self)
        self.options: list[PPlayer] = []
        self.actors: list[PPlayer] = []
        self.died: list[PPlayer] = []
        self.data: dict[str, Any] = {}

        roles = Counter(self.roles)
        self.data['roles'] = ', '.join(
            f'{num} {Pl.__name__.lower()}' for Pl, num in roles.items()
        )

        random.shuffle(self.chars)
        random.shuffle(self.roles)
        for seat, (char, Pl) in enumerate(zip(self.chars, self.roles)):
            self.players.append(Pl(self, char, Seat(seat)))

    def __str__(self) -> str:
        info_player = '\n\t'.join(str(pl) for pl in self.players)
        return f'[{self.time}]players: \n\t{info_player}'

    def boardcast(self, pls: Iterable[PPlayer], content: str) -> None:
        info = Info(copy(self.time), (), tuple(pls), content)
        self.info.append(info)
        output_info(info)

    def unicast(self, pl: PPlayer, content: str) -> None:
        self.boardcast((pl,), content)

    def loop(self) -> None:
        start_message = f"players: \n\t{'\n\t'.join(pl.str_public() for pl in self.players)}"
        output_info(
            Info(
                copy(self.time),
                (),
                tuple(self.audience()),
                f'{start_message}\n',
            ),
            console=True,
            clear_text=f'Please wait...\nThe upper line for input.\n',
        )
        for pl in self.players:
            self.unicast(pl, f'You are a {pl.role.kind}.')

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
            self.badge.badge()
            self.time.inc_phase()
            try:
                self.day()
            except SelfExposureError as e:
                pass
            if self.exec():
                break
            if self.post_exec():
                break
            self.badge.badge()

        winner = self.winner()
        end_message = f'{winner.faction} win.\n' 'winners:\n\t' + '\n\t'.join(
            str(pl) for pl in self.players if winner.eq_faction(pl.role)
        ) + '\n' + str(self)
        output_info(
            Info(copy(self.time), (), tuple(self.audience()), end_message),
            console=True,
        )

    def day(self) -> None:
        self.died = [
            pl
            for pl in self.audience()
            if any(
                death.time.cycle == self.time.cycle - 1
                and death.time.phase == Phase.NIGHT
                for death in pl.death
            )
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
        for pl in speakers:
            speech = speech_expose(pl, 'make a speech to everyone')
            pl.boardcast(self.audience(), speech)
        self.options = list(self.alived())

        # vote
        self.time.inc_stage()
        targets = self.vote(
            self.options, self.options, 'your vote to eliminate a player'
        )
        if not targets:
            pass
        elif isinstance(targets, PPlayer):
            targets.death.append(
                Info(copy(self.time), tuple(self.options), (targets,), 'vote')
            )
            targets.life = False
            self.testament((targets,))
        else:
            self.time.inc_stage()
            targets.reverse()
            for pl in targets:
                speech = speech_expose(pl, 'give the additional speech')
                pl.boardcast(self.audience(), speech)
            targets = self.vote(
                targets, self.options, 'vote again to eliminate a player'
            )
            if not targets:
                pass
            elif isinstance(targets, PPlayer):
                targets.death.append(
                    Info(
                        copy(self.time),
                        tuple(self.options),
                        (targets,),
                        'vote',
                    )
                )
                targets.life = False
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
            self.time.inc_stage()
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
            self.time.inc_stage()
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
        task: str,
        silent: bool = False,
    ) -> None | PPlayer | list[PPlayer]:
        candidates = list(candidates_iter)
        voters = list(voters_iter)
        ballot = {pl: 0.0 for pl in candidates}
        abstain = 0
        vote_text = ''
        votes = async_input_op(voters, task, candidates, ('pass',))
        for pl, vote in zip(voters, votes):
            sign = ''
            if pl.vote == 1.5:
                sign = '*'
            elif pl.vote == 0.0:
                sign = '†'
            if vote == 'pass':
                abstain += 1
                vote_text += f'{pl.seat}{sign}->pass, '
            else:
                ballot[str2pl(self, vote)] += pl.vote
                vote_text += f'{pl.seat}{sign}->{str2pl(self, vote).seat}, '
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
                    f'Seat {pls2str(targets)} ended in a tie. Vote result: {vote_text[:-2]}.',
                )
            return targets

    def testament(self, died: Iterable[PPlayer]) -> None:
        self.time.inc_stage()
        for pl in died:
            speech = input_speech(pl, 'You are dying, any last words?')
            pl.boardcast(self.audience(), speech)

    def audience(self) -> Generator[PPlayer]:
        return (pl for pl in self.players)

    def audience_role(self, role: str) -> Generator[PPlayer]:
        return (pl for pl in self.players if pl.role.kind == role)

    def alived(self) -> Generator[PPlayer]:
        return (pl for pl in self.players if pl.life)

    def alived_role(self, role: str) -> Generator[PPlayer]:
        return (pl for pl in self.players if pl.life and pl.role.kind == role)
