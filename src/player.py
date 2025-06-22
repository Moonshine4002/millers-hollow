from .header import *

from .io import Input, Output, output_info, get_inputs, async_get_inputs


def empty(mark: Mark) -> None:
    pass


def kill(mark: Mark) -> None:
    for t in mark.info.target:
        t.killed(mark)


def filtration(mark: Mark, elem: str) -> None:
    for t in mark.info.target:
        t.marks.reset(filter(lambda mark: mark.name != elem, t.marks))


def expose(mark: Mark) -> None:
    game = mark.info.game
    for t in mark.info.target:
        t.killed(mark)
        game.verdict()
        game.boardcast(
            game.audience(),
            f'Seat {t.seat} (a {t.role.faction}) self-exposed!',
        )
    game.time.time_set(datetime.time(18))
    raise TimeChangedError('expose')


class BPlayer:
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        self.game = game
        self.char = char
        self.seat = seat
        self.life = True
        role = self.__class__.__name__.lower()
        self.role = Role(role, role, role)
        self.skills: dict[str, Skill] = {}
        self.marks = Marks(self)
        self.death = Marks(self)
        self.tasks: list[Input] = []
        self.results: list[Output] = []

        self.vote = 1.0
        self.can_expose = False
        self.skills['vote'] = kill
        self.skills['expose'] = expose

    def __str__(self) -> str:
        life = '☥' if self.life else '†'
        return f'{self.seat}{life} {self.role.kind} {self.char.name}({self.char.model}): {self.char.description}'

    def str_public(self) -> str:
        return f'{self.seat} {self.char.name}({self.char.model}): {self.char.description}'

    @staticmethod
    def cast(info: Info) -> None:
        info.game.info.append(info)
        output_info(info)

    def boardcast(self, pls: Iterable[PPlayer], content: str) -> None:
        info = Info(
            self.game, copy(self.game.time), (self,), tuple(pls), content
        )
        self.cast(info)

    def receive(self, content: str) -> None:
        info = Info(self.game, copy(self.game.time), (), (self,), content)
        self.cast(info)

    def loop(self) -> None:
        if self.game.time.state == State.DAY:
            self.day()
        elif self.game.time.state == State.NIGHT:
            self.night()

    def day(self) -> None:
        ...

    def night(self) -> None:
        ...

    def dying(self) -> None:
        ...

    def verdict(self) -> None:
        if all(pl.role.eq_faction(self.role) for pl in self.game.options):
            self.game.winner = self.role
            self.game.time.state = State.END
            raise TimeChangedError('game over')

    def exec(self) -> None:
        self.marks.exec()

    def killed(self, mark: Mark) -> None:
        self.death.append(mark)
        if self.life:
            self.game.died.append(self)
            self.life = False

    def expose(self) -> None:
        self.marks.add_exec('expose', (self,))


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
        if expose != 'expose':
            return speech
        pl.expose()
    return input_speech(pl, prompt)


def speech_quit_expose(pl: PPlayer, prompt: str) -> tuple[str, str]:
    if pl.can_expose:
        speech, quit, expose = input_speech_quit_expose(pl, prompt)
        if expose != 'expose':
            return speech, quit
        pl.expose()
    return input_speech_quit(pl, prompt)


class Villager(BPlayer):
    ...


class Werewolf(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        if user_data.allow_exposure:
            self.can_expose = True
        self.skills['claw'] = kill

    def verdict(self) -> None:
        if user_data.win_condition == 'all':
            super().verdict()
            return
        pls = list(
            filter(
                lambda pl: not pl.role.eq_faction(self.role), self.game.options
            )
        )
        if not pls or all(pl.role.eq_category(pls[0].role) for pl in pls):
            self.game.winner = self.role
            self.game.time.state = State.END
            TimeChangedError('game over')

    def night(self) -> None:
        if self.game.time.datetime.time() != datetime.time(0):
            return
        actors = list(
            filter(lambda pl: pl.role.faction == 'werewolf', self.game.options)
        )
        if self != actors[0]:
            return
        self.game.boardcast(
            actors,
            f'Werewolves {pls2str(actors)}, please open your eyes!',
        )
        for pl in actors:
            if len(actors) == 1:
                break
            speech = input_speech(pl, 'talk with your teammates')
            pl.boardcast(actors, speech)
        targets = self.game.vote(
            self.game.options,
            actors,
            'choose one player to kill',
            silent=True,
        )
        if not targets:
            self.game.boardcast(actors, 'Werewolves kill nobody.')
            return
        random.shuffle(targets)
        target = targets[0]
        target.marks.add('claw', actors)
        self.game.boardcast(actors, f'Werewolves kill seat {target.seat}.')


def white(mark: Mark) -> None:
    game = mark.info.game
    for t in mark.info.target:
        t.killed(mark)
        game.verdict()
        choice = input_op(
            t,
            'pass or choose a player to kill',
            game.options,
            ('pass',),
        )
        if choice == 'pass':
            game.boardcast(
                game.audience(),
                f'Seat {t.seat} (a {t.role.faction}) self-exposed!',
            )
        else:
            game.boardcast(
                game.audience(),
                f'Seat {t.seat} (a {t.role.kind}) self-exposed!',
            )
            pl = str2pl(game, choice)
            game.boardcast(
                game.audience(),
                f'Seat {t.seat} killed seat {pl.seat}.',
            )
            pl.killed(mark)
    game.time.time_set(datetime.time(18))
    raise TimeChangedError('expose')


class WhiteWolf(Werewolf):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'werewolf'
        self.role.category = 'god'

        self.skills['expose'] = white


def seer(mark: Mark) -> None:
    for s, t in zip(mark.info.source, mark.info.target):
        s.receive(f'Seat {t.seat} is a {t.role.faction}.')


class Seer(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'

        self.skills['seer'] = seer

    def night(self) -> None:
        if self.game.time.datetime.time() != datetime.time(0):
            return
        self.receive('Seer, please open your eyes!')
        choice = input_op(
            self, 'the player you want to check', self.game.options
        )
        pl = str2pl(self.game, choice)
        pl.marks.add_exec('seer', (self,))


class Witch(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'

        self.antidote = True
        self.poison = True
        self.skills['antidote'] = functools.partial(filtration, elem='claw')
        self.skills['poison'] = kill

    def night(self) -> None:
        if self.game.time.datetime.time() != datetime.time(1):
            return
        self.receive('Witch, please open your eyes!')
        target: PPlayer | None = None
        for mark in itertools.chain.from_iterable(
            pl.marks for pl in self.game.options
        ):
            if mark.name == 'claw':
                target = mark.info.target[0]
        if self.antidote:
            target_str = f'seat {target.seat}' if target else 'nobody'
            self.receive(
                f'Tonight {target_str} has been killed by the werewolves.'
            )
        self.receive(
            f'You have {int(self.antidote)} antidote and {int(self.poison)} poison.',
        )
        antidote = (
            self.antidote
            and target
            and not (
                target == self
                and self.game.time.datetime.day != self.game.time.start.day + 1
            )
        )
        poison = self.poison
        if antidote and poison:
            choice = input_op(
                self,
                'pass, save, or choose a player to poison',
                self.game.options,
                ('save', 'pass'),
            )
        elif antidote:
            choice = input_op(self, 'pass or save', op2=('save', 'pass'))
        elif poison:
            choice = input_op(
                self,
                'pass or choose a player to poison',
                self.game.options,
                ('pass',),
            )
        else:
            return
        if choice == 'pass':
            return
        elif choice == 'save':
            self.antidote = False
            if target is None:
                raise RuntimeError('wrong choice')
            target.marks.add('antidote', (self,), 1)
        else:
            self.poison = False
            pl = str2pl(self.game, choice)
            pl.marks.add('poison', (self,), 1)


def gun(mark: Mark) -> None:
    game = mark.info.game
    for s in mark.info.source:
        game.boardcast(game.audience(), f'Seat {s.seat} is a {s.role.kind}!')
        if any('poison' == mark.name for mark in s.death):
            return
        choice = input_op(
            s,
            'you are dying, pass or choose a player to shoot',
            game.options,
            ('pass',),
        )
        if choice == 'pass':
            game.boardcast(
                game.audience(),
                f"Seat {s.seat} didn't shoot anyone.",
            )
            return
        pl = str2pl(game, choice)
        game.boardcast(
            game.audience(),
            f'Seat {s.seat} shot seat {pl.seat}.',
        )
        pl.killed(mark)


class Hunter(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'

        self.gun = True
        self.skills['gun'] = gun

    def dying(self) -> None:
        if self.life:
            return
        if not self.gun:
            return
        self.gun = False
        self.marks.add('gun', (self,))


class BlackWolf(Werewolf, Hunter):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'werewolf'


def shield(mark: Mark) -> None:
    for t in mark.info.target:
        if any(mark.name == 'antidote' for mark in t.marks):
            filtration(mark, 'antidote')
            return
        filtration(mark, 'werewolf')


class Guard(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'

        self.guard: PPlayer | None = None
        self.skills['shield'] = shield

    def night(self) -> None:
        if self.game.time.datetime.time() != datetime.time(23):
            return
        self.receive('Guard, please open your eyes!')
        options = list(
            filter(lambda option: option != self.guard, self.game.options)
        )
        choice = input_op(
            self, 'who will you protect tonight?', options, ('pass',)
        )
        if choice == 'pass':
            self.guard = None
            return
        pl = str2pl(self.game, choice)
        self.guard = pl
        pl.marks.add('shield', (self,), priority=2)


def vote_fool(mark: Mark) -> None:
    game = mark.info.game
    for t in mark.info.target:
        if not isinstance(t, Fool):
            raise RuntimeError('wrong player')
        game.boardcast(game.audience(), f'Seat {t.seat} is a {t.role.kind}!')
        t.exposed = True
        t.vote = 0.0


class Fool(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'

        self.exposed = False
        self.skills['vote'] = vote_fool


def duel(mark: Mark) -> None:
    game = mark.info.game
    for s in mark.info.source:
        s.can_expose = False
        game.boardcast(
            game.audience(),
            f'Seat {s.seat} (a {s.role.kind}) self-exposed!',
        )
        choice = input_op(
            s,
            'choose a player to duel',
            game.options,
        )
        pl = str2pl(game, choice)
        game.boardcast(
            game.audience(),
            f'Seat {s.seat} duel with seat {pl.seat}.',
        )
        if pl.role.faction == 'werewolf':
            game.boardcast(
                game.audience(),
                f'Seat {pl.seat} is a werewolf',
            )
            pl.killed(mark)
            game.time.time_set(datetime.time(18))
            raise TimeChangedError('expose')
        else:
            game.boardcast(
                game.audience(),
                f'Seat {pl.seat} is not a werewolf',
            )
            s.killed(mark)
            game.died.remove(s)


class Knight(BPlayer):
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        super().__init__(game, char, seat)
        self.role.faction = 'villager'
        self.role.category = 'god'

        self.can_expose = True
        self.skills['expose'] = duel


class Badge:
    def __init__(self, game: PGame) -> None:
        self.owner: PPlayer | None = None
        self.game = game

    def election(self) -> None:
        candidates: list[PPlayer] = []
        quitters: list[PPlayer] = []
        self.game.boardcast(
            self.game.audience(),
            "It's time to run for the sheriff.",
        )
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
        elif len(targets) == 1:
            target = targets[0]
            self.owner = target
            target.vote = 1.5
            user_data.election_round = 0
        else:
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
            elif len(targets) == 1:
                target = targets[0]
                self.owner = target
                target.vote = 1.5
                user_data.election_round = 0
            else:
                pass

    def transfer(self) -> None:
        if not self.owner:
            return
        if self.owner.life == False:
            self.game.boardcast(
                self.game.audience(),
                'The former sheriff is passing the badge.',
            )
            choice = input_op(
                self.owner,
                'You are dying. Say "destroy" to destroy the badge or choose a player to transfer the badge.',
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
        self.info: list[Info] = []
        self.badge: PBadge = Badge(self)

        self.winner = Role('')
        self.options: list[PPlayer] = []
        self.died: list[PPlayer] = []

        ran_chars = copy(self.chars)
        ran_roles = copy(self.roles)
        random.shuffle(ran_chars)
        random.shuffle(ran_roles)
        for seat, (char, Pl) in enumerate(zip(ran_chars, ran_roles)):
            self.players.append(Pl(self, char, Seat(seat)))
        self.verdict()

    def __str__(self) -> str:
        info_player = '\n\t'.join(str(pl) for pl in self.players)
        return f'players: \n\t{info_player}'

    def boardcast(self, pls: Iterable[PPlayer], content: str) -> None:
        info = Info(self, copy(self.time), (), tuple(pls), content)
        BPlayer.cast(info)

    def unicast(self, pl: PPlayer, content: str) -> None:
        info = Info(self, copy(self.time), (), (pl,), content)
        BPlayer.cast(info)

    def loop(self) -> None:
        start_message = f"players: \n\t{'\n\t'.join(pl.str_public() for pl in self.players)}"
        output_info(
            Info(
                self,
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

        roles_counter = Counter(self.roles)
        setup = ', '.join(
            f'{num} {Pl.__name__.lower()}' for Pl, num in roles_counter.items()
        )
        self.boardcast(
            self.audience(),
            "This game is called The Werewolves of Miller's Hollow. "
            f'The game setup is {setup}. '
            f'Players list from seat 1 to {len(self.players)}.',
        )

        while True:
            try:
                match self.time.state:
                    case State.BEGIN:
                        self.time.time_set(datetime.time(18))
                        raise TimeChangedError('begin')
                    case State.DAY:
                        self.day()
                    case State.NIGHT:
                        self.night()
                    case State.END:
                        break
            except TimeChangedError as e:
                try:
                    while self.died:
                        self.verdict()
                        for pl in self.died:
                            pl.dying()
                        self.died.clear()
                        self.exec()
                except TimeChangedError as e:
                    pass
            else:
                self.time.time_inc()

        end_message = (
            f'{self.winner.faction} win.\n'
            'winners:\n\t'
            + '\n\t'.join(
                str(pl)
                for pl in self.players
                if self.winner.eq_faction(pl.role)
            )
            + '\n'
            + str(self)
        )
        output_info(
            Info(
                self, copy(self.time), (), tuple(self.audience()), end_message
            ),
            console=True,
        )

    def day(self) -> None:
        match self.time.datetime.hour:
            case 6:
                self.boardcast(
                    self.audience(),
                    "It's daytime. Everyone woke up.",
                )
            case 7:  # sheriff
                if user_data.election_round:
                    user_data.election_round -= 1
                    self.badge.election()
            case 8:  # announcement
                self.exec()
                self.died.sort(key=lambda pl: pl.seat)
                self.boardcast(
                    self.audience(),
                    (
                        f'Seat {pls2str(self.died)} are killed last night. '
                        if self.died
                        else 'Nobody died last night. '
                    )
                    + f'Seat {pls2str(self.alived())} are still alive.',
                )
            case 9:  # verdict
                while self.died:
                    self.verdict()
                    if self.time.datetime.day == self.time.start.day + 1:
                        self.testament()
                    for pl in self.died:
                        pl.dying()
                    self.died.clear()
                    self.exec()
            case 12:  # speech
                speakers = self.badge.speakers()
                for pl in speakers:
                    speech = speech_expose(pl, 'make a public speaking')
                    pl.boardcast(self.audience(), speech)
            case 13:  # vote
                targets = self.vote(
                    self.options,
                    self.options,
                    'your vote to eliminate a player',
                )
                if not targets:
                    pass
                elif len(targets) == 1:
                    target = targets[0]
                    target.marks.add('vote', self.options)
                else:
                    targets.reverse()
                    for pl in targets:
                        speech = speech_expose(pl, 'extra public speaking')
                        pl.boardcast(self.audience(), speech)
                    targets = self.vote(
                        targets,
                        self.options,
                        'vote again to eliminate a player',
                    )
                    if not targets:
                        pass
                    elif len(targets) == 1:
                        target = targets[0]
                        target.marks.add('vote', self.options)
                self.exec()
            case 14:  # verdict
                while self.died:
                    self.verdict()
                    self.testament()
                    for pl in self.died:
                        pl.dying()
                    self.died.clear()
                    self.exec()
        for pl in self.options:
            pl.day()

    def night(self) -> None:
        match self.time.datetime.hour:
            case 18:
                self.boardcast(
                    self.audience(),
                    f"It's dark, Everyone close your eyes. Seat {pls2str(self.alived())} are still alive.",
                )
        for pl in self.options:
            pl.night()

    def verdict(self) -> None:
        self.options = list(self.alived())
        for pl in self.options:
            pl.verdict()
        self.badge.transfer()

    def exec(self) -> None:
        for pl in self.players:
            pl.exec()

    def testament(self) -> None:
        if not self.died:
            raise RuntimeError('no died')
        self.died.sort(key=lambda pl: pl.seat)
        self.boardcast(
            self.audience(), f'Seat {pls2str(self.died)} are dying.'
        )
        for pl in self.died:
            speech = input_speech(
                pl, 'you are dying, make the last public speaking'
            )
            pl.boardcast(self.audience(), speech)

    def vote(
        self,
        candidates_iter: Iterable[PPlayer],
        voters_iter: Iterable[PPlayer],
        task: str,
        silent: bool = False,
    ) -> list[PPlayer]:
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
            return []
        highest = max(ballot.values())
        targets = [pl for pl, value in ballot.items() if value == highest]
        if not silent:
            if len(targets) == 1:
                target = targets[0]
                self.boardcast(
                    self.audience(),
                    f'Seat {target.seat} got the highest votes. Vote result: {vote_text[:-2]}.',
                )
            else:
                self.boardcast(
                    self.audience(),
                    f'Seat {pls2str(targets)} ended in a tie. Vote result: {vote_text[:-2]}.',
                )
        return targets

    def audience(self) -> Generator[PPlayer]:
        return (pl for pl in self.players)

    def alived(self) -> Generator[PPlayer]:
        return (pl for pl in self.players if pl.life)
