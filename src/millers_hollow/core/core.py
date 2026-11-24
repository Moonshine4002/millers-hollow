import asyncio
import random
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Self

from pydantic import BaseModel, Field

from millers_hollow.llm.llm import LLM
from millers_hollow.localization.manager import tr
from millers_hollow.util.log import logger

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
                    if record.speaker.role.faction != listener.role.faction:
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
class Role:
    role: str
    faction: str


class Player:
    def __init__(self, seat: int, name: str, model: str, role: Role) -> None:
        self.seat = seat
        self.name = name
        self.model = model
        self.role = role
        self.life = True

    def public_info(self) -> str:
        seat = tr('player.seat', seat=self.seat)
        life = tr(f'player.life.{str(self.life).lower()}')
        return tr('player.public', seat=seat, name=self.name, life=life)


class Game:
    PROMPT_TEMPLATE = tr('prompt.template')

    def __init__(self, roles: Sequence[Role]) -> None:
        self.logger = logger()
        self.output_bus = OutputBus()
        self.consumer_tasks: list[asyncio.Task[None]] = []
        self.history = History()
        self.llm = LLM()
        self.roles = list(roles)
        self.players: list[Player] = []
        self.restart()

    async def __aenter__(self) -> Self:
        async def cli_consumer(queue: asyncio.Queue[Output]) -> None:
            try:
                while True:
                    output = await queue.get()
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
                            raise ValueError(
                                f'unknown output channel: {output.channel}'
                            )
            except asyncio.QueueShutDown:
                pass

        async def log_consumer(queue: asyncio.Queue[Output]) -> None:
            try:
                while True:
                    output = await queue.get()
                    if output.stream:
                        continue
                    self.logger.info('[%s] %s', output.channel, output.content)
            except asyncio.QueueShutDown:
                pass

        cli_queue = self.output_bus.subscribe()
        log_queue = self.output_bus.subscribe()
        self.consumer_tasks = [
            asyncio.create_task(cli_consumer(cli_queue)),
            asyncio.create_task(log_consumer(log_queue)),
        ]

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.output_bus.close()
        await asyncio.gather(*self.consumer_tasks)

    def restart(self) -> None:  # TODO: reset all game state
        self.history = History()
        # self.llm = LLM()
        roles = random.sample(self.roles, len(self.roles))
        self.players.clear()
        for i, role in enumerate(roles):
            player = Player(
                seat=i + 1,
                name=tr('player.seat', seat=i + 1),
                model='ollama-local',  # temp
                role=role,
            )
            self.players.append(player)
        self.players[random.randint(1, len(roles) - 1)].model = 'human'  # temp

    def get_player(self, seat: int) -> Player:
        return self.players[seat - 1]  # TODO: use No.

    async def get_message(
        self, seat: int, channel: str, task: str, action: type[BaseModel]
    ) -> str:
        player = self.get_player(seat)
        player_info = '\n'.join(f'- {player.public_info()}' for player in self.players)
        history_msg = '\n'.join(self.history.get_record(player))
        stream_prompt = self.PROMPT_TEMPLATE.format(
            seat=tr('player.seat', seat=seat),
            name=player.name,
            role=tr(f'role.{player.role.role}'),
            faction=tr(f'faction.{player.role.faction}'),
            skill=tr(f'skill.{player.role.role}'),
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
                for player in self.players
                if player.life and player.role.faction == 'innocents'
            )
        )
        mafiosi = len(
            tuple(
                player
                for player in self.players
                if player.life and player.role.faction == 'mafiosi'
            )
        )
        if mafiosi == 0:
            self.narration(tr('game.win.mafiosi'))
            return 'innocents'
        elif mafiosi - innocents > 0:
            self.narration(tr('game.win.innocents'))
            return 'mafiosi'
        return ''

    async def loop(self) -> None:
        night_start = tr('game.night_start')
        self.narration(night_start)
        discussion: list[int] = []
        for player in self.players:
            if not player.life or player.role.faction != 'mafiosi':
                continue
            content = await self.get_message(
                player.seat, 'team', tr('task.kill'), ActionKill
            )
            discussion.append(int(content))
        died = discussion[0]  # temp
        self.history.update_progress()

        if not discussion:
            day_start = tr(
                'game.day_start', last_night=tr('game.day_start.peaceful_night')
            )
        else:
            narration = ', '.join(f'{tr("player.seat", seat=seat)}' for seat in [died])
            day_start = tr(
                'game.day_start',
                last_night=tr('game.day_start.player_died', died=narration),
            )
        self.narration(day_start)
        self.get_player(died).life = False
        self.narration(
            f'{tr("player.seat", seat=died)}{tr("base.is")}{tr(f"faction.{self.get_player(died).role.faction}")}'
        )
        if self.end():
            return
        self.narration(tr('game.speech'))
        for player in self.players:
            if not player.life:
                continue
            await self.get_message(
                player.seat, 'public', tr('task.speech'), ActionSpeech
            )
        self.narration(tr('game.vote'))
        players = [player for player in self.players if player.life]
        gathered = await asyncio.gather(
            *(
                self.get_message(player.seat, 'public', tr('task.vote'), ActionVote)
                for player in players
            )
        )
        votes = list(
            zip(
                (player.seat for player in players),
                (int(content) for content in gathered),
            )
        )
        voted = Counter(vote[1] for vote in votes).most_common(1)[0][0]  # temp
        self.get_player(voted).life = False
        self.narration(
            tr(
                'game.vote_result',
                result=','.join(f'{vote[0]}->{vote[1]}' for vote in votes),
                voted=tr('player.seat', seat=voted),
                faction=tr(f'faction.{self.get_player(voted).role.faction}'),
            )
        )
        if self.end():
            return
        self.history.update_progress()


async def main() -> None:
    innocent = Role(role='innocent', faction='innocents')
    mafioso = Role(role='mafioso', faction='mafiosi')
    async with Game([innocent, innocent, innocent, innocent, mafioso]) as game:
        while not game.end():
            await game.loop()


if __name__ == '__main__':
    asyncio.run(main())
