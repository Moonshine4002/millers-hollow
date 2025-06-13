from openai import OpenAI, AsyncOpenAI
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam,
)

from .header import *


client = OpenAI(
    api_key=user_data.api_key,
    base_url=user_data.base_url,
)

system_prompt = (
    "You are playing a game called The Werewolves of Miller's Hollow. "
    'Please be sure that you know the rules. '
    'You will be given a input describing the game scenario. '
    'Try your best to win the game.\n\n'
    'Rules:\n'
    '- The Moderator is always truthful.\n'
    '- You win if your team wins.\n'
    '- Output must use "---" as separation.\n'
    f'- Output using "{user_data.language}".\n\n'
    'Game rules:\n'
    f'- Werewolves win by eliminating {user_data.win_condition} villagers.\n'
    f"- Werewolves can {'not' if not user_data.allow_exposure else ''} expose themselves."
    f'- The sheriff election continues for {user_data.election_round} rounds.\n'
    '- Players killed on the first night or eliminated by vote have a dying speech.\n'
    "- The seer's verification only reveals whether the target belongs to the good faction, not their specific role.\n"
    '- The witch cannot use the antidote to save herself except for the first night.\n'
    '- The hunter cannot shoot after poisoned by the witch.\n'
    '- The guard cannot protect the same player for two consecutive nights.\n'
    '- Simultaneous protection by the witch and guard on the same target has no effect.\n'
    '- The fool is still alived after being voted out, the werewolves may need to chase and eliminate them.\n\n'
    'Tips:\n'
    "- Avoid repeating others' statements.\n"
    '- You can reveal your true role or impersonate another role (regardless of your faction).\n'
    '- When impersonating, fully develop your thought process and reasoning.\n\n'
    f'{user_data.additional_prompt}'
)


class Input(NamedTuple):
    prompt: str
    options: list[str] = []

    def __str__(self) -> str:
        options = f' replaced by one of {self.options}' if self.options else ''
        return f'["{self.prompt}"{options}]'


class Output(NamedTuple):
    output: str


log_time = Time()
log_time_str = time.strftime('%y-%m-%d-%H-%M-%S')


def log(content: str, clear_text: str = '') -> None:
    log_path = pathlib.Path(f'{log_time_str}.log')
    if clear_text:
        log_path.write_text(clear_text, encoding='utf-8')
    with log_path.open(mode='a', encoding='utf-8') as file:
        file.write(content)


def output(
    pls_iter: Iterable[PPlayer],
    clue: Clue,
    system: bool = False,
    clear_text: str = '',
) -> None:
    global log_time
    pls = list(pls_iter)
    if log_time == clue.time:
        log(
            f'\t{clue.source}> {clue.content} > {pls2str(pls)}\n',
            clear_text=clear_text,
        )
    else:
        log_time = clue.time
        log(
            f'[{clue.time}]\n\t{clue.source}> {clue.content} > {pls2str(pls)}\n',
            clear_text=clear_text,
        )
    if system or any(pl.char.control == 'console' for pl in pls):
        print(str(clue))
    for pl in pls:
        if pl.char.control != 'file':
            continue
        file_path = pathlib.Path(f'io/{pl.seat}.txt')
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if clear_text:
            file_path.write_text(clear_text, encoding='utf-8')
        with file_path.open(mode='a', encoding='utf-8') as file:
            file.write(f'{clue}\n')


def input_ai(pl: PPlayer, messages: list[ChatCompletionMessageParam]) -> str:
    chat_completion = client.chat.completions.create(
        model=pl.char.model,
        messages=messages,
    )
    content = chat_completion.choices[0].message.content
    if not content:
        raise ValueError('empty output')
    return content


def get_console_inputs(pl: PPlayer, inputs: Iterable[Input]) -> list[Output]:
    outputs: list[Output] = []
    print(f'Task: {pl.task}')
    for i in inputs:
        outputs.append(Output(input(f'{i.prompt}: ')))
    for i, o in zip(inputs, outputs):
        if i.options and o.output not in i.options:
            raise ValueError(f'wrong value: {o.output}')
    return outputs


def get_ai_inputs(pl: PPlayer, inputs_iter: Iterable[Input]) -> str:
    inputs = list(inputs_iter)
    messages: list[ChatCompletionMessageParam] = [
        {'role': 'system', 'content': system_prompt}
    ]
    for clue in pl.clues:
        message: ChatCompletionMessageParam = {
            'role': 'user',
            'content': clue.content,
            'name': clue.source,
        }
        messages.append(message)
    prompt = (
        f'You are seat {pl.seat}, a {pl.role.kind}.\n'
        f'Your personality: {pl.char.description}\n'
        f'Your task: {pl.task}\n'
        f'Output format: {" --- ".join(str(i) for i in inputs)}'
    )
    messages.append({'role': 'system', 'content': prompt})
    return input_ai(pl, messages)


def get_file_inputs(pl: PPlayer, inputs_iter: Iterable[Input]) -> list[Output]:
    inputs = list(inputs_iter)
    file_path = pathlib.Path(f'io/{pl.seat}.txt')
    prompt = ' --- '.join(str(i) for i in inputs)
    with file_path.open('r', encoding='utf-8') as file:
        lines = file.readlines()
    if not lines or len(lines) < 2:
        raise ValueError('empty file')
    lines[0] = f'{prompt}\n'
    lines[1] = f'Task: {pl.task}\n'
    with file_path.open('w', encoding='utf-8') as file:
        file.writelines(lines)
    while True:
        time.sleep(1)
        with file_path.open('r', encoding='utf-8') as file:
            lines = file.readlines()
        if not lines:
            raise ValueError('empty file')
        if lines[0].strip() == prompt:
            continue
        output = parse(pl, inputs, lines[0])
        lines[0] = f'Please wait...\n'
        with file_path.open('w', encoding='utf-8') as file:
            file.writelines(lines)
        return output


def parse(
    pl: PPlayer, inputs_iter: Iterable[Input], content: str
) -> list[Output]:
    inputs = list(inputs_iter)
    content = content.replace('\n', ' ')
    if len(inputs) == 1:
        lcontent = [content]
    else:
        if '---' not in content:
            raise ValueError(f'wrong format: 0 "---"')
        lcontent = content.split('---')
        if len(lcontent) != len(inputs):
            raise ValueError(f'wrong format: {len(lcontent) - 1} "---"')
    outputs = [Output(content.strip(' \'"[]').lower()) for content in lcontent]
    for i, o in zip(inputs, outputs):
        if i.options and o.output not in i.options:
            raise ValueError(f'wrong value: {o.output}')
    return outputs


def get_inputs(pl: PPlayer, inputs_iter: Iterable[Input]) -> list[Output]:
    inputs_iter = itertools.chain(
        (
            Input('your seat, ability, task'),
            Input("summary of the game state and known players' identities"),
            Input('your immediate action and long term strategy'),
        ),
        inputs_iter,
        (Input('your remarks'),),
    )
    inputs = list(inputs_iter)
    if not pl.task:
        raise ValueError('empty task')
    while True:
        try:
            match pl.char.control:
                case 'console':
                    outputs = get_console_inputs(pl, inputs)
                case 'ai':
                    content = get_ai_inputs(pl, inputs)
                    outputs = parse(pl, inputs, content)
                case 'file':
                    outputs = get_file_inputs(pl, inputs)
                case _:
                    raise NotImplementedError('unknown control')
        except NotImplementedError as e:
            raise
        except Exception as e:
            log(f'\t{e!r}\n')
        else:
            output_str = ' --- '.join(
                f'{i.prompt}: {o.output}' for i, o in zip(inputs, outputs)
            )
            log(f'\t{pl.seat}[{pl.role.kind}]~> {output_str}\n')
            (info, summary, strategy, *outputs, remarks) = outputs
            pl.task = ''
            return outputs


def input_word(pl: PPlayer, candidates_iter: Iterable[str]) -> str:
    (choice,) = get_inputs(
        pl,
        (Input(pl.task, list(candidates_iter)),),
    )
    return choice.output


def input_speech(pl: PPlayer) -> str:
    (speech,) = get_inputs(pl, (Input(pl.task),))
    return speech.output


def input_speech_quit(pl: PPlayer) -> tuple[str, str]:
    speech, quit = get_inputs(
        pl,
        (
            Input(pl.task),
            Input('Will you quit the election?', ['quit', 'no']),
        ),
    )
    return speech.output, quit.output


def input_speech_expose(pl: PPlayer) -> tuple[str, str]:
    speech, expose = get_inputs(
        pl,
        (
            Input(pl.task),
            Input('Will you make a self-exposure?', ['expose', 'no']),
        ),
    )
    return speech.output, expose.output


def input_speech_quit_expose(pl: PPlayer) -> tuple[str, str, str]:
    speech, quit, expose = get_inputs(
        pl,
        (
            Input(pl.task),
            Input('Will you quit the election?', ['quit', 'no']),
            Input('Will you make a self-exposure?', ['expose', 'no']),
        ),
    )
    return speech.output, quit.output, expose.output


async_client = AsyncOpenAI(
    api_key=user_data.api_key,
    base_url=user_data.base_url,
)


async def async_input_ai(
    pl: PPlayer, messages: list[ChatCompletionMessageParam]
) -> str:
    chat_completion = await async_client.chat.completions.create(
        model=pl.char.model,
        messages=messages,
    )
    content = chat_completion.choices[0].message.content
    if not content:
        raise ValueError('empty output')
    return content


async def async_get_console_inputs(
    pl: PPlayer, inputs: Iterable[Input]
) -> list[Output]:
    outputs: list[Output] = []
    print(f'Task: {pl.task}')
    for i in inputs:
        outputs.append(Output(input(f'{i.prompt}: ')))
    for i, o in zip(inputs, outputs):
        if i.options and o.output not in i.options:
            raise ValueError(f'wrong value: {o.output}')
    return outputs


async def async_get_ai_inputs(
    pl: PPlayer, inputs_iter: Iterable[Input]
) -> str:
    inputs = list(inputs_iter)
    messages: list[ChatCompletionMessageParam] = [
        {'role': 'system', 'content': system_prompt}
    ]
    for clue in pl.clues:
        message: ChatCompletionMessageParam = {
            'role': 'user',
            'content': clue.content,
            'name': clue.source,
        }
        messages.append(message)
    prompt = (
        f'You are seat {pl.seat}, a {pl.role.kind}.\n'
        f'Your personality: {pl.char.description}\n'
        f'Your task: {pl.task}\n'
        f'Output format: {" --- ".join(str(i) for i in inputs)}'
    )
    messages.append({'role': 'system', 'content': prompt})
    return await async_input_ai(pl, messages)


async def async_get_file_inputs(
    pl: PPlayer, inputs_iter: Iterable[Input]
) -> list[Output]:
    inputs = list(inputs_iter)
    file_path = pathlib.Path(f'io/{pl.seat}.txt')
    prompt = ' --- '.join(str(i) for i in inputs)
    with file_path.open('r', encoding='utf-8') as file:
        lines = file.readlines()
    if not lines or len(lines) < 2:
        raise ValueError('empty file')
    lines[0] = f'{prompt}\n'
    lines[1] = f'Task: {pl.task}\n'
    with file_path.open('w', encoding='utf-8') as file:
        file.writelines(lines)
    while True:
        await asyncio.sleep(1)
        with file_path.open('r', encoding='utf-8') as file:
            lines = file.readlines()
        if not lines:
            raise ValueError('empty file')
        if lines[0].strip() == prompt:
            continue
        output = parse(pl, inputs, lines[0])
        lines[0] = f'Please wait...\n'
        with file_path.open('w', encoding='utf-8') as file:
            file.writelines(lines)
        return output


async def async_get_inputs(
    pl: PPlayer, inputs_iter: Iterable[Input]
) -> list[Output]:
    inputs_iter = itertools.chain(
        (
            Input('your seat, ability, task'),
            Input("summary of the game state and known players' identities"),
            Input('your immediate action and long term strategy'),
        ),
        inputs_iter,
        (Input('your remarks'),),
    )
    inputs = list(inputs_iter)
    if not pl.task:
        raise ValueError('empty task')
    while True:
        try:
            match pl.char.control:
                case 'console':
                    outputs = await async_get_console_inputs(pl, inputs)
                case 'ai':
                    content = await async_get_ai_inputs(pl, inputs)
                    outputs = parse(pl, inputs, content)
                case 'file':
                    outputs = await async_get_file_inputs(pl, inputs)
                case _:
                    raise NotImplementedError('unknown control')
        except NotImplementedError as e:
            raise
        except Exception as e:
            log(f'\t{e!r}\n')
        else:
            output_str = ' --- '.join(
                f'{i.prompt}: {o.output}' for i, o in zip(inputs, outputs)
            )
            log(f'\t{pl.seat}[{pl.role.kind}]~> {output_str}\n')
            (info, summary, strategy, *outputs, remarks) = outputs
            pl.task = ''
            return outputs


async def async_input_words(
    pls: Iterable[PPlayer], candidates_iter: Iterable[str]
) -> Iterable[str]:
    candidates = list(candidates_iter)
    results = await asyncio.gather(
        *(async_get_inputs(pl, (Input(pl.task, candidates),)) for pl in pls)
    )
    choices = itertools.chain.from_iterable(results)
    return (choice.output for choice in choices)
