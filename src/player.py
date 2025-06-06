from .header import *

from .io import input_speech, input_word
from . import user_data


class BPlayer:
    def __init__(self, game: PGame, char: Char, seat: Seat) -> None:
        self.game = game
        self.char = char
        role = self.__class__.__name__.lower()
        self.role = Role(role, role, role)
        self.life = True
        self.seat = seat
        self.night_priority = 0
        self.clues: list[Clue] = []
        self.death_time: Time = Time()
        self.death_causes: list[str] = []

    def __str__(self) -> str:
        life = '☥' if self.life else '†'
        return f'{life}{self.char.name}({self.seat})[{self.role.kind}]'

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
        self.night_priority = 3   # TODO

    def night(self) -> None:
        def func(game: PGame, source: PPlayer, target: PPlayer) -> None:
            target.life = False
            target.death_time = copy(game.time)
            target.death_causes.append(self.role.kind)

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
        targets = self.game.vote(self.game.options, self.game.actors)
        if targets is None:
            self.game.data['target_for_witch'] = None
        elif isinstance(targets, PPlayer):
            self.game.marks.append(
                Mark(self.role.kind, self.game, self, targets, func)
            )
            self.game.data['target_for_witch'] = pl
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
            source.antidote = False
            game.marks = [
                mark
                for mark in game.marks
                if not (mark.target == target and mark.name == 'werewolf')
            ]

        def func_p(game: PGame, source: PPlayer, target: PPlayer) -> None:
            assert isinstance(source, self.__class__)
            source.poison = False
            target.life = False
            target.death_time = copy(game.time)
            target.death_causes.append(self.role.kind)

        self.receive('Witch, please open your eyes!')
        target: PPlayer | None = self.game.data['target_for_witch']
        if self.antidote:
            target_str = (
                f'seat {target.seat}' if target is not None else 'nobody'
            )
            self.receive(
                f'Tonight {target_str} has been killed by the werewolves.'
            )
        decisions = []
        if self.antidote and target is not None:
            decisions.append('save')
        if self.poison:
            decisions.extend(pls2lstr(self.game.options))
        if not decisions:
            return
        self.receive(
            f'You have {int(self.antidote)} antidote and {int(self.poison)} poison. '
            'Say "pass" to pass, say "save" to save, say a seat to kill a player of that seat.'
        )
        str_ = self.str_optional(decisions)
        if str_ == 'pass':
            pass
        elif str_ == 'save':
            assert isinstance(target, PPlayer)
            self.game.marks.append(
                Mark('antidote', self.game, self, target, func_a, priority=1)
            )
        else:
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
            pl = self.pl_optional(game.options)
            if pl is None:
                return
            pl.life = False
            pl.death_time = copy(game.time)
            pl.death_causes.append(self.role.kind)
            game.boardcast(
                game.audience(), f'Seat {source.seat} shoot seat {pl.seat}.'
            )

        self.__life = value
        if self.__life:
            return
        if 'witch' in self.death_causes:   # TODO
            return
        self.game.post_marks.append(
            Mark(self.role.kind, self.game, self, self, func, priority=1)
        )


class Game:
    def __init__(self) -> None:
        self.time = Time()
        self.chars = [Char(name, 'ai') for name in string.ascii_uppercase]
        self.roles: list[type[PPlayer]] = [
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
        self.players: list[PPlayer] = []
        self.marks: list[Mark] = []
        self.post_marks: list[Mark] = []

        users = len(user_data.user_names)
        ai = len(self.roles) - users
        if ai < 0:
            raise ValueError('too many users')
        chars = random.sample(self.chars, ai)
        for user_name in user_data.user_names:
            chars.append(Char(user_name, 'file'))
        random.shuffle(chars)
        random.shuffle(self.roles)
        for seat, role in enumerate(self.roles):
            self.players.append(role(self, chars[seat], Seat(seat)))

        self.options: list[PPlayer] = []
        self.actors: list[PPlayer] = []
        self.data: dict[str, Any] = {}

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
            clear_text=f'Input: \nThe upper line for input.\n',
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
            'The game setup is 3 villagers, 3 werewolves, 1 seer, 1 witch, and 1 hunter. '
            f'Players list from seat 1 to {len(self.options)}.',
        )

        while True:
            self.time.inc_phase()
            self.night()
            if self.exec():
                break
            if self.post_exec():
                break
            self.time.inc_phase()
            self.day()
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
        died = [
            pl
            for pl in self.audience()
            if pl.death_time.cycle == self.time.cycle - 1
            and pl.death_time.phase == Phase.NIGHT
        ]
        summary = (
            f'Seat {pls2str(died)} are killed last night. '
            if died
            else 'Nobody died last night. '
        )
        self.boardcast(
            self.audience(),
            f"It's daytime. Everyone woke up. {summary}Seat {pls2str(self.options)} are still alive.",
        )
        if self.time.cycle == 1:
            self.testament(died)

        # speech
        self.boardcast(
            self.audience(),
            f'Now freely talk about the current situation based on your observation with a few sentences.',
        )
        for pl in self.options:
            speech = input_speech(pl)
            pl.boardcast(self.audience(), speech)

        # vote
        self.time.inc_round()
        self.boardcast(self.audience(), f"It's time to vote.")
        targets = self.vote(self.options, self.options)
        if targets is None:
            pass
        elif isinstance(targets, PPlayer):
            targets.life = False
            self.testament((targets,))
        else:
            self.time.inc_round()
            targets = self.vote(targets, self.options)
            if targets is None:
                pass
            elif isinstance(targets, PPlayer):
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
        elif count_villagers + count_god == 0:   # count_villagers * count_god
            return Role('werewolf')
        elif count_werewolfs == 0:
            return Role('villager')
        # elif count_villagers + count_god < count_werewolfs:
        #    return Role('werewolf')
        else:
            return Role('')

    def vote(
        self,
        candidates_iter: Iterable[PPlayer],
        voters_iter: Iterable[PPlayer],
        silent: bool = False,
    ) -> None | PPlayer | list[PPlayer]:
        candidates = list(candidates_iter)
        voters = list(voters_iter)
        ballot = {pl: 0 for pl in candidates}
        abstain = 0
        vote_text = ''
        for pl in voters:
            vote = pl.pl_optional(candidates)
            if vote is None:
                abstain += 1
                vote_text += f'{pl.seat}->pass, '
            else:
                ballot[vote] += 1
                vote_text += f'{pl.seat}->{vote.seat}, '
        if abstain == len(voters):
            if not silent:
                self.boardcast(voters, 'Everyone passed.')
            return None
        highest = max(ballot.values())
        targets = [pl for pl, value in ballot.items() if value == highest]
        if len(targets) == 1:
            target = targets[0]
            if not silent:
                self.boardcast(
                    voters,
                    f'Seat {target.seat} got the highest votes. Vote result: {vote_text[:-2]}.',
                )
            return target
        else:
            if not silent:
                self.boardcast(
                    voters,
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
