import asyncio
import random
import string
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import singledispatchmethod
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from millers_hollow.llm.llm import LLM
from millers_hollow.localization.manager import tr
from millers_hollow.util.log import Logger

from .bus import Output, OutputBus


class ActionSpeech(BaseModel):
    reason: str = Field(description=tr('action.reason'))
    speech: str = Field(description=tr('action.speech'))
    summary: str = Field(description=tr('action.summary'))


class ActionVote(BaseModel):
    reason: str = Field(description=tr('action.reason'))
    eliminate: int = Field(description=tr('action.eliminate'))


class ActionKill(BaseModel):
    reason: str = Field(description=tr('action.reason'))
    discussion: str = Field(description=tr('action.discussion'))
    kill: int = Field(description=tr('action.kill'))


@dataclass(frozen=True)
class Progress:
    round: int
    phase: str

    def __str__(self) -> str:
        return tr('progress', round=self.round, phase=tr(f'progress.{self.phase}'))


@dataclass(frozen=True)
class Record:
    progress: Progress
    content: str
    speaker: Player | None
    channel: str
    tags: tuple[str, ...] = ()


class History:
    def __init__(self) -> None:
        self.restart()

    def restart(self) -> None:
        self.data: list[Record] = []
        self.progress = Progress(1, 'night')

    def get_record(self, listener: Player) -> Iterator[str]:
        for record in self.data:
            if record.speaker is None:
                yield f'[narration] {record.content}'
                continue
            match record.channel:
                case 'public':
                    pass
                case 'team':
                    if record.speaker.faction != listener.faction:
                        continue
                case _:
                    raise ValueError(f'unknown record channel: {record.channel}')
            yield f'[{record.speaker.name}] {record.content}'

    def add_record(
        self,
        content: str,
        speaker: Player | None,
        channel: str,
        tags: Sequence[str] = (),
    ) -> None:
        self.data.append(Record(self.progress, content, speaker, channel, tuple(tags)))

    def update_progress(self) -> None:
        if self.progress.phase == 'night':
            self.progress = Progress(self.progress.round, 'day')
        else:
            self.progress = Progress(self.progress.round + 1, 'night')


@dataclass(frozen=True)
class Character:
    uuid: UUID
    name: str
    model: str


@dataclass(frozen=True)
class Occupation:
    role: str
    faction: str
    skills: tuple[str, ...] = ()


innocent = Occupation(role='innocent', faction='innocents', skills=('speech', 'vote'))
mafioso = Occupation(
    role='mafioso', faction='mafiosi', skills=('speech', 'vote', 'kill')
)
mafia_setup = [innocent, innocent, innocent, innocent, mafioso]  # temp


class Player:
    def __init__(self, char: Character, occ: Occupation, seat: int) -> None:
        self.uuid = char.uuid
        self.name = char.name
        self.model = char.model
        self.restart(occ, seat)

    def restart(self, occ: Occupation, seat: int) -> None:
        self.role = occ.role
        self.faction = occ.faction
        self.skills: list[str] = list(occ.skills)
        self.seat = seat
        self.life = True
        self.tags: list[str] = []

    def public_info(self) -> str:
        seat = tr('player.seat', seat=self.seat)
        life = tr(f'player.life.{str(self.life).lower()}')
        return tr('player.public', seat=seat, name=self.name, life=life)


class Game:
    PROMPT_TEMPLATE = tr('prompt.template')

    def __init__(self, chars: Sequence[Character], occs: Sequence[Occupation]) -> None:
        self.logger = Logger()
        self.output_bus = OutputBus()
        self.history = History()
        self.llm = LLM()
        self.chars = list(chars)
        self.occs = list(occs)
        self.restart()

    async def __aenter__(self) -> Self:
        async def cli_consumer(queue: asyncio.Queue[Output]) -> None:
            while True:
                try:
                    output = await queue.get()
                except asyncio.QueueShutDown:
                    break
                match output.channel:
                    case 'narration':
                        print(output.content)
                    case 'content':
                        if not output.stream:
                            continue
                        if not output.end:
                            print(output.content, end='', flush=True)
                            continue
                        print(output.content)
                    case 'reasoning' | 'prompt' | 'summary':
                        pass
                    case _:
                        raise ValueError(f'unknown output channel: {output.channel}')

        async def log_consumer(queue: asyncio.Queue[Output]) -> None:
            while True:
                try:
                    output = await queue.get()
                except asyncio.QueueShutDown:
                    break
                if output.stream:
                    continue
                self.logger.logger.info('[%s] %s', output.channel, output.content)

        self.output_bus.subscribe(cli_consumer)
        self.output_bus.subscribe(log_consumer)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.output_bus.close()

    def restart(self) -> None:
        self.logger.restart()
        self.history.restart()
        self.llm.restart()
        chars = random.sample(self.chars, len(self.occs))
        occs = random.sample(self.occs, len(self.occs))
        self.players: dict[UUID, Player] = {}
        for i, (char, occ) in enumerate(zip(chars, occs)):
            self.players[char.uuid] = Player(char, occ, i + 1)
        random.choice(tuple(self.players.values())).model = 'human'  # temp

    @singledispatchmethod
    def get_player(self, attr) -> Player:
        raise NotImplementedError(f'not implemented type: {type(attr)}')

    @get_player.register
    def _(self, attr: UUID) -> Player:
        return self.players[attr]

    @get_player.register
    def _(self, attr: int) -> Player:
        for player in self.players.values():
            if player.seat == attr:
                return player
        raise ValueError(f'unknown seat: {attr}')

    async def get_message(
        self, uuid: UUID, channel: str, task: str, action: type[BaseModel]
    ) -> str:
        player = self.get_player(uuid)
        player_info = '\n'.join(
            f'- {player.public_info()}' for player in self.players.values()
        )
        history_msg = '\n'.join(self.history.get_record(player))
        stream_prompt = self.PROMPT_TEMPLATE.format(
            seat=tr('player.seat', seat=player.seat),
            name=player.name,
            role=tr(f'role.{player.role}'),
            faction=tr(f'faction.{player.faction}'),
            skill=tr(f'skill.{player.role}'),
            players_info=player_info,
            rules=tr('rule'),
            progress=str(self.history.progress),
            history=history_msg,
            task=task,
            output_format=tr('format'),
        )
        self.output_bus.publish(Output(stream_prompt, 'prompt'))
        if player.model == 'human':  # temp
            raw = await asyncio.to_thread(input, f'{task}{tr("base.colon")}')  # temp
        else:
            raw = await self.llm.stream_chat(
                player.model, stream_prompt, self.output_bus
            )

        structured_prompt = f'{raw}\n{tr("prompt.summary")}'
        self.output_bus.publish(Output(structured_prompt, 'prompt'))
        structured = await self.llm.structured_chat(
            'ollama-local',
            structured_prompt,
            action,
            self.output_bus,
        )
        match structured:
            case ActionSpeech():
                self.history.add_record(structured.summary, player, channel)
                return structured.speech
            case ActionVote():
                return str(structured.eliminate)
            case ActionKill():
                self.history.add_record(structured.discussion, player, channel)
                return str(structured.kill)
            case _:
                raise ValueError(f'unknown action: {action!r}')

    def narration(self, narration: str) -> None:
        self.history.add_record(narration, None, 'public')
        self.output_bus.publish(Output(narration, 'narration'))

    def end(self) -> str:
        innocents = len(
            tuple(
                player
                for player in self.players.values()
                if player.life and player.faction == 'innocents'
            )
        )
        mafiosi = len(
            tuple(
                player
                for player in self.players.values()
                if player.life and player.faction == 'mafiosi'
            )
        )
        if mafiosi == 0:
            self.narration(tr('game.win.innocents'))
            return 'innocents'
        elif mafiosi >= innocents:
            self.narration(tr('game.win.mafiosi'))
            return 'mafiosi'
        return ''

    async def loop(self) -> None:
        night_start = tr('game.night_start')
        self.narration(night_start)
        discussion: list[Player] = []
        for player in self.players.values():
            if not player.life or player.faction != 'mafiosi':
                continue
            content = await self.get_message(
                player.uuid, 'team', tr('task.kill'), ActionKill
            )
            discussion.append(self.get_player(int(content)))
        died = discussion[0]  # temp
        self.history.update_progress()

        if not discussion:
            day_start = tr(
                'game.day_start', last_night=tr('game.day_start.peaceful_night')
            )
        else:
            narration = ', '.join(
                f'{tr("player.seat", seat=player.seat)}' for player in (died,)
            )
            day_start = tr(
                'game.day_start',
                last_night=tr('game.day_start.player_died', died=narration),
            )
        self.narration(day_start)
        died.life = False
        self.narration(
            f'{tr("player.seat", seat=died.seat)}{tr("base.is")}{tr(f"faction.{died.faction}")}'
        )
        if self.end():
            return
        self.narration(tr('game.speech'))
        for player in self.players.values():
            if not player.life:
                continue
            await self.get_message(
                player.uuid, 'public', tr('task.speech'), ActionSpeech
            )
        self.narration(tr('game.vote'))
        players = [player for player in self.players.values() if player.life]
        gathered = await asyncio.gather(
            *(
                self.get_message(player.uuid, 'public', tr('task.vote'), ActionVote)
                for player in players
            )
        )
        votes = list(
            zip(
                (player.seat for player in players),
                (int(content) for content in gathered),
            )
        )
        voted = self.get_player(
            Counter(vote[1] for vote in votes).most_common(1)[0][0]
        )  # temp
        voted.life = False
        self.narration(
            tr(
                'game.vote_result',
                result=','.join(f'{vote[0]}->{vote[1]}' for vote in votes),
                voted=tr('player.seat', seat=voted.seat),
                faction=tr(f'faction.{voted.faction}'),
            )
        )
        if self.end():
            return
        self.history.update_progress()


async def main() -> None:
    chars = [
        Character(uuid4(), name, 'ollama-local') for name in string.ascii_uppercase
    ]  # temp

    async with Game(chars, mafia_setup) as game:
        while not game.end():
            await game.loop()


if __name__ == '__main__':
    asyncio.run(main())
