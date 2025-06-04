from .header import *

from .ai import get_speech, get_word
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
        self.night_priority = 0
        self.clues: list[Clue] = []
        self.death_causes: list[str] = []

    def __str__(self) -> str:
        life = '☥' if self.life else '†'
        return f'{life}{self.character.name}(seat {self.role.seat})[{self.role.role}]'

    def boardcast(self, audiences: Sequence[Seat], content: str) -> None:
        game.boardcast(audiences, content, str(self.role.seat))

    def receive(self, content: str) -> None:
        game.unicast(self.role.seat, content)

    def night(self) -> None:
        ...

    @overload
    def choose_seat(
        self, candidates: Sequence[Seat], abstain: Literal[True] = True
    ) -> Seat | None:
        ...

    @overload
    def choose_seat(
        self, candidates: Sequence[Seat], abstain: Literal[False]
    ) -> Seat:
        ...

    def choose_seat(
        self, candidates: Sequence[Seat], abstain: bool = True
    ) -> Seat | None:
        candidates_str = [str(candidate) for candidate in candidates]
        if abstain:
            candidates_str.append('pass')
        answer = get_word(self, candidates_str)
        if answer == 'pass':
            return None
        else:
            return Seat(answer)

    def choose_word(self, candidates: Sequence[str]) -> str:
        return get_word(self, candidates)


class Villager(BPlayer):
    ...


class Werewolf(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        super().__init__(character, role)
        role.faction.faction = 'werewolf'
        self.night_priority = 3

    def night(self) -> None:
        def mark(source: Seat, target: Seat) -> None:
            game.players[target].death_causes.append('werewolf')
            game.players[target].life = False

        if self.role.seat != game.actors[0]:
            return

        game.boardcast(
            game.actors,
            f'Werewolves, please open your eyes! '
            f'I secretly tell you that seat {game.actors} are all of the {len(game.actors)} werewolves! '
            f'Now you can talk secretly with your teammates.',
        )
        for seat in game.actors:
            werewolf = game.players[seat]
            speech = get_speech(werewolf)
            werewolf.boardcast(game.actors, speech)
        game.boardcast(
            game.actors, f'Werewolves, now you can choose one player to kill.'
        )
        targets = game.vote(game.options, game.actors)
        match targets:
            case None:
                game.data['target_for_witch'] = None
            case Seat(seat):
                game.marks.append(
                    Mark(self.role.role, self.role.seat, seat, mark)
                )
                game.data['target_for_witch'] = seat
                game.boardcast(
                    game.actors, f'Werewolves kill seat {seat} together.'
                )
            case _:
                game.marks.append(
                    Mark(self.role.role, self.role.seat, targets[0], mark)
                )
                game.data['target_for_witch'] = targets[0]
                game.boardcast(
                    game.actors,
                    f'Werewolves kill seat {targets[0]} in spite of disagreement.',
                )


class Seer(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        super().__init__(character, role)
        role.faction.category = 'god'
        self.night_priority = 1

    def night(self) -> None:
        self.receive('Seer, please open your eyes!')
        self.receive(
            f"Seer, you can check one player's identity. Who are you going to verify its identity tonight? "
            f'Choose one from the following living options please: seat {game.options}.',
        )
        target = self.choose_seat(game.options, abstain=False)
        self.receive(
            f'Seat {target} is {game.players[target].role.faction.faction}.'
        )


class Witch(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        super().__init__(character, role)
        role.faction.category = 'god'
        self.night_priority = 2

        self.antidote = True
        self.poison = True

    def night(self) -> None:
        def antidote(source: Seat, target: Seat) -> None:
            source_player = game.players[source]
            target_player = game.players[target]
            if not isinstance(source_player, Witch):
                raise TypeError('mark source is not a witch')
            source_player.antidote = False
            game.marks = [
                mark
                for mark in game.marks
                if not (
                    mark.target == target
                    and mark.name == Werewolf.__name__.lower()
                )
            ]

        def poison(source: Seat, target: Seat) -> None:
            source_player = game.players[source]
            target_player = game.players[target]
            if not isinstance(source_player, Witch):
                raise TypeError('mark source is not a witch')
            source_player.poison = False
            target_player.death_causes.append('witch')
            target_player.life = False

        self.receive('Witch, please open your eyes!')
        target_for_witch = game.data['target_for_witch']
        decisions = ['pass']
        if self.antidote and target_for_witch is not None:
            decisions.append('save')
            target_for_witch_str = (
                f'seat {target_for_witch}'
                if target_for_witch is not None
                else 'nobody'
            )
            self.receive(
                f'Witch, I secretly tell you that tonight {target_for_witch_str} has been killed by the werewolves.'
            )
        if self.poison:
            decisions.extend(str(option) for option in game.options)
        if decisions == ['pass']:
            return
        self.receive(
            f'Witch, you have {int(self.antidote)} antidote and {int(self.poison)} poison. Your options are {decisions}. '
            'Say "pass" to pass, say "save" to save, say a seat to kill a player of that seat.'
        )
        decision = self.choose_word(decisions).lower()
        match decision:
            case 'pass':
                pass
            case 'save':
                if target_for_witch is None:
                    raise RuntimeError(
                        "target_for_witch's type is not as expected"
                    )
                game.marks.append(
                    Mark(
                        'antidote',
                        self.role.seat,
                        Seat(target_for_witch),
                        antidote,
                        priority=1,
                    )
                )
            case seat:
                game.marks.append(
                    Mark(
                        'poison',
                        self.role.seat,
                        Seat(seat),
                        poison,
                        priority=1,
                    )
                )


class Hunter(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        super().__init__(character, role)
        role.faction.category = 'god'

    @property
    def life(self) -> bool:
        return self.__life

    @life.setter
    def life(self, value: bool) -> None:
        def mark(source: Seat, target: Seat) -> None:
            game.boardcast(
                game.audience(), f'Seat {self.role.seat} is a hunter!'
            )
            game.boardcast(
                [self.role.seat],
                f'Please choose a living player ({game.alived()}) to shoot or pass.',
            )
            seat = self.choose_seat(game.alived())
            if seat is None:
                return

            game.players[seat].death_causes.append('hunter')
            game.players[seat].life = False
            game.boardcast(
                game.audience(), f'Seat {source} shoot seat {seat}.'
            )

        self.__life = value
        if self.__life:
            return
        if 'witch' in self.death_causes:
            return
        game.post_marks.append(
            Mark(
                self.role.role,
                self.role.seat,
                self.role.seat,
                mark,
                priority=1,
            )
        )


class Game:
    def __init__(self) -> None:
        self.time = Time()
        self.players: list[PPlayer] = []
        self.marks: list[Mark] = []
        self.post_marks: list[Mark] = []

        self.characters = [
            InfoCharacter(name, 'ai') for name in string.ascii_uppercase
        ]

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

        users = len(user_data.user_names)
        ai = len(self.roles) - users
        if ai < 0:
            raise ValueError('too many users')
        characters = random.sample(self.characters, ai)
        for user_name in user_data.user_names:
            characters.append(InfoCharacter(user_name, 'file'))
        random.shuffle(characters)
        random.shuffle(self.roles)
        for seat, role in enumerate(self.roles):
            self.players.append(role(characters[seat], InfoRole(seat)))

        self.options: list[Seat] = []
        self.actors: list[Seat] = []
        self.data: dict[str, Any] = {}

    def __str__(self) -> str:
        info_player = '\n\t'.join(str(player) for player in self.players)
        return f'[{self.time}]players: \n\t{info_player}'

    def output(
        self,
        audiences: Sequence[Seat],
        clue: Clue,
        system: bool = False,
        clear_text: str = '',
    ) -> None:
        log(f'{clue} > {audiences}\n', clear_text=clear_text)
        if system or any(
            self.players[seat].character.control == 'console'
            for seat in audiences
        ):
            print(str(clue))
        for seat in audiences:
            player = self.players[seat]
            if player.character.control != 'file':
                continue
            file_path = pathlib.Path(f'io/{player.role.seat}.txt')
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if clear_text:
                file_path.write_text(clear_text, encoding='utf-8')
            with file_path.open(mode='a', encoding='utf-8') as file:
                file.write(f'{clue}\n')

    def boardcast(
        self,
        audiences: Sequence[Seat],
        content: str,
        source: str = 'Moderator',
    ) -> None:
        clue = Clue(copy(self.time), source, content)
        for seat in audiences:
            self.players[seat].clues.append(clue)
        self.output(audiences, clue)

    def unicast(self, seat: Seat, content: str) -> None:
        self.boardcast([seat], content)

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

    def night(self) -> None:
        self.options = self.alived()
        actions: dict[int, list[Seat]] = {}
        for player in self.players:
            if not player.life:
                continue
            actions.setdefault(player.night_priority, []).append(
                player.role.seat
            )
        while actions:
            game.time.inc_round()
            self.actors = actions.pop(max(actions))
            for seat in self.actors:
                game.players[seat].night()

    def vote(
        self,
        candidates: Sequence[Seat],
        voters: Sequence[Seat],
        silent: bool = False,
    ) -> None | Seat | list[Seat]:
        self.boardcast(voters, f'Please vote in {candidates} or pass.')
        ballot = [0] * (len(self.players) + 1)
        vote_text = ''
        for seat in voters:
            vote = self.players[seat].choose_seat(candidates)
            if vote is None:
                ballot[-1] += 1
                vote_text += f'{seat}->pass, '
            else:
                ballot[vote] += 1
                vote_text += f'{seat}->{vote}, '
        if ballot[-1] == len(voters):
            self.boardcast(voters, 'Everyone passed.')
            return None
        ballot = ballot[:-1]
        highest = max(ballot)
        targets = [
            seat for seat, value in enumerate(ballot) if value == highest
        ]
        if len(targets) == 1:
            target = targets[0]
            if not silent:
                self.boardcast(
                    voters,
                    f'Seat {target} got the highest votes. Vote result: {vote_text[:-2]}.',
                )
            return target
        else:
            if not silent:
                self.boardcast(
                    voters,
                    f"It's a tie. Vote result: {vote_text[:-2]}.",
                )
            return targets

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
        self.options = self.alived()
        self.boardcast(
            self.audience(),
            "It's dark, everyone close your eyes. I will talk with you/your team secretly at night.",
        )

        # night
        game.night()

        # exec
        self.exec()

        # day
        self.time.inc_phase()
        audiences_died = [
            audience
            for audience in self.options
            if audience not in self.alived()
        ]
        self.options = self.alived()
        summary = (
            f'Seat {audiences_died} are killed last night.'
            if audiences_died
            else 'Nobody died last night.'
        )
        self.boardcast(
            self.audience(),
            f"It's daytime. Everyone woke up. {summary} Seat {self.options} are still alive.",
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
        self.options = self.alived()

        # speech
        self.boardcast(
            self.audience(),
            f'Now freely talk about the current situation based on your observation with a few sentences.',  # (round 1/2).',
        )
        for seat in self.options:
            player = self.players[seat]
            speech = get_speech(player)
            player.boardcast(self.audience(), speech)
        """
        self.boardcast(
            self.audience(),
            f'Now freely talk about the current situation based on your observation with a few sentences (round 2/2).',
        )
        for seat in alived_old:
            player = self.players[seat]
            speech = get_speech(player)
            player.boardcast(self.audience(), speech)
        """

        # vote
        self.time.inc_round()
        self.boardcast(
            self.audience(),
            f"It's time to vote.",
        )

        targets = self.vote(self.options, self.options)
        match targets:
            case None:
                pass
            case Seat(seat):
                self.players[seat].life = False
            case _:
                targets = self.vote(targets, self.options)
                match targets:
                    case None:
                        pass
                    case Seat(seat):
                        self.players[seat].life = False
                    case _:
                        pass

        # verdict
        audiences_died = [
            audience
            for audience in self.options
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
start_message = f"players: \n\t{'\n\t'.join(f'{player.character.name}(seat {player.role.seat})' for player in game.players)}"
game.output(
    game.audience(),
    Clue(game.time, 'Moderator', f'{start_message}\n'),
    system=True,
    clear_text=f'Input: \nThe upper line for input.\n',
)
for player in game.players:
    game.unicast(
        player.role.seat,
        f'You are seat {player.role.seat}, a {player.role.role}.',
    )

# rule
game.boardcast(
    game.audience(),
    "This game is called The Werewolves of Miller's Hollow. "
    'The game setup is 3 villagers, 3 werewolves, 1 seer, 1 witch, and 1 hunter. Players list from seat 0 to 8.',
)


while not game.loop():
    pass

winner = game.winner()
end_message = f'{winner} win.\n' 'winners:\n\t' + '\n\t'.join(
    str(player)
    for player in game.players
    if winner.eq_faction(player.role.faction)
) + '\n' + str(game)
game.output(
    game.audience(), Clue(game.time, 'Moderator', end_message), system=True
)
