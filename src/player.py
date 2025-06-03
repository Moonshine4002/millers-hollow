from .header import *

from .ai import get_seat, get_speech, get_word
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

    def mark(self, target: Seat) -> Mark:
        raise NotImplementedError('mark not implemented')

    def choose(self, candidates: Sequence[Seat]) -> Seat:
        return get_seat(self, candidates)


class Villager(BPlayer):
    ...


class Werewolf(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        super().__init__(character, role)
        role.faction.faction = 'werewolf'
        self.night_priority = 3

    def night(self) -> None:
        if self.role.seat == game.actors[0]:
            game.boardcast(
                game.actors,
                f'Werewolves, please open your eyes! I secretly tell you that seat {game.actors} are all of the {len(game.actors)} werewolves!',
            )
            game.boardcast(
                game.actors,
                f'Now you can talk with your teammates.',
            )
            for seat in game.actors:
                werewolf = game.players[seat]
                speech = get_speech(werewolf)
                werewolf.boardcast(game.actors, speech)
            game.boardcast(
                game.actors,
                (
                    f'Werewolves, you can choose one player to kill. Who are you going to kill tonight? '
                    f'Choose one from the following living options to kill please: seat {game.options}. '
                    '(The player with the highest vote count will be selected. In case of a tie, the one with the smallest seat number will be chosen.)'
                ),
            )
            targets, record = game.vote(game.options, game.actors)
            target = targets[0]
            mark = self.mark(target)
            game.marks.append(mark)
            game.data['target_for_witch'] = target

    def mark(self, target: Seat) -> Mark:
        def func(source: Seat, target: Seat) -> None:
            game.players[target].death_causes.append('werewolf')
            game.players[target].life = False

        return Mark(self.role.role, self.role.seat, target, func)


class Seer(BPlayer):
    def __init__(self, character: InfoCharacter, role: InfoRole) -> None:
        super().__init__(character, role)
        role.faction.category = 'god'
        self.night_priority = 1

    def night(self) -> None:
        self.receive('Seer, please open your eyes!')
        self.receive(
            f"Seer, you can check one player's identity. Who are you going to verify its identity tonight? Choose one from the following living options please: seat {game.options}.",
        )
        target = self.choose(game.options)
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
        self.potion_decision = 'pass'

    def night(self) -> None:
        self.receive('Witch, please open your eyes! ')
        decision = 'pass'
        if self.antidote:
            self.receive(
                f'Witch, I secretly tell you that tonight seat {game.data["target_for_witch"]} has been killed by the werewolves. You have a bottle of antidote, would you like to save him/her? If so, say "save", else, say "pass".',
            )
            decision = get_word(self, ['save', 'pass']).lower()
            if decision == 'save':
                self.potion_decision = 'antidote'
                mark = self.mark(game.data['target_for_witch'])
                game.marks.append(mark)
        if decision == 'pass' and self.poison:
            self.receive(
                f'Witch you decided whether to use the antidote previously. Now you also have a bottle of poison, would you like to use it to kill one of the living players? If so, say "kill", else, say "pass".',
            )
            decision = get_word(self, ['kill', 'pass']).lower()
        if decision == 'kill':
            self.potion_decision = 'poison'
            self.receive(
                f'Choose one from the following living options: {game.options}.',
            )
            seat = get_seat(self, game.options)
            mark = self.mark(seat)
            game.marks.append(mark)

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
        super().__init__(character, role)
        role.faction.category = 'god'

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
        self.data: dict[str, Seat] = {}

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

        # night
        game.night()

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
            f'Now freely talk about the current situation based on your observation with a few sentences (round 1/2).',
        )
        for seat in alived_old:
            player = self.players[seat]
            speech = get_speech(player)
            player.boardcast(self.audience(), speech)
        self.boardcast(
            self.audience(),
            f'Now freely talk about the current situation based on your observation with a few sentences (round 2/2).',
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
game.output(
    game.audience(), Clue(game.time, 'Moderator', end_message), system=True
)
