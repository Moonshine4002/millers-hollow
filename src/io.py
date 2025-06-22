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


log_time = Time()
log_name = time.strftime('%y-%m-%d-%H-%M-%S')


def log(content: str, clear_text: str = '') -> None:
    log_path = pathlib.Path(f'io/{log_name}.log')
    if clear_text:
        log_path.write_text(clear_text, encoding='utf-8')
    with log_path.open(mode='a', encoding='utf-8') as file:
        file.write(content)


def output_info(
    info: Info,
    console: bool = False,
    clear_text: str = '',
) -> None:
    global log_time
    if info.time.eq_step(log_time):
        text = f'\t{pls2str(info.source)}> {info.content}'
    else:
        text = str(info)
    log_time = info.time
    log(f'{text} > {pls2str(info.target)}\n', clear_text)
    if console or any(pl.char.control == 'console' for pl in info.target):
        print(info)
    for pl in info.target:
        if pl.char.control != 'file':
            continue
        file_path = pathlib.Path(f'io/{pl.seat}.txt')
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if clear_text:
            file_path.write_text(clear_text, encoding='utf-8')
        with file_path.open(mode='a', encoding='utf-8') as file:
            file.write(f'{text}\n')


def get_console_inputs(pl: PPlayer) -> None:
    pl.results.clear()
    print(f'Major task: {pl.tasks[3].prompt}')
    for i in pl.tasks:
        while True:
            o = input(f'{i.prompt}: ')
            if i.options and o not in i.options:
                continue
            pl.results.append(Output(o))


def parse(pl: PPlayer, content: str) -> None:
    content = content.replace('\n', ' ')
    if '---' not in content:
        raise ValueError(f'wrong format: 0 "---"')
    lcontent = content.split('---')
    if len(lcontent) != len(pl.tasks):
        raise ValueError(f'wrong format: {len(lcontent) - 1} "---"')
    pl.results = [
        Output(content.strip(' \'"[]').lower()) for content in lcontent
    ]
    for i, o in zip(pl.tasks, pl.results):
        if i.options and o.output not in i.options:
            raise ValueError(f'wrong value: {o.output}')


def input_ai(pl: PPlayer, messages: list[ChatCompletionMessageParam]) -> str:
    chat_completion = client.chat.completions.create(
        model=pl.char.model,
        messages=messages,
    )
    content = chat_completion.choices[0].message.content
    if not content:
        raise ValueError('empty output')
    return content


def get_ai_inputs(pl: PPlayer) -> None:
    messages: list[ChatCompletionMessageParam] = [
        {'role': 'system', 'content': system_prompt}
    ]
    for info in pl.game.info:
        if pl not in info.target:
            continue
        message: ChatCompletionMessageParam = {
            'role': 'user',
            'content': info.content,
            'name': pls2str(info.source),
        }
        messages.append(message)
    prompt = (
        f'You are seat {pl.seat}, a {pl.role.kind}.\n'
        f'Your personality: {pl.char.description}\n'
        f'Your task: Replace the content in the square brackets with your answer.\n'
        f'Output format: {" --- ".join(str(task) for task in pl.tasks)}'
    )
    messages.append({'role': 'system', 'content': prompt})
    content = input_ai(pl, messages)
    parse(pl, content)


def get_file_inputs(pl: PPlayer) -> None:
    file_path = pathlib.Path(f'io/{pl.seat}.txt')
    prompt = ' --- '.join(str(task) for task in pl.tasks)
    with file_path.open('r', encoding='utf-8') as file:
        lines = file.readlines()
    if not lines or len(lines) < 2:
        raise ValueError('empty file')
    lines[0] = f'{prompt}\n'
    lines[1] = f'Major task: {pl.tasks[3].prompt}\n'
    with file_path.open('w', encoding='utf-8') as file:
        file.writelines(lines)
    while True:
        time.sleep(1)
        with file_path.open('r', encoding='utf-8') as file:
            lines = file.readlines()
        if not lines:
            raise ValueError('empty file')
        content = lines[0].strip()
        if content == prompt:
            continue
        parse(pl, content)
        lines[0] = f'Please wait...\n'
        with file_path.open('w', encoding='utf-8') as file:
            file.writelines(lines)
        break


def get_inputs(pl: PPlayer) -> None:
    if not pl.tasks:
        raise ValueError('empty task')
    pl.tasks[:0] = [
        Input('your seat, ability, task'),
        Input("summary of the game state and known players' identities"),
        Input('your immediate action and long term strategy'),
    ]
    pl.tasks.append(Input('unpublished annotations'))
    while True:
        try:
            match pl.char.control:
                case 'console':
                    get_console_inputs(pl)
                case 'ai':
                    get_ai_inputs(pl)
                case 'file':
                    get_file_inputs(pl)
                case _:
                    raise NotImplementedError('unknown control')
        except NotImplementedError as e:
            raise
        except Exception as e:
            output_info(Info(pl.game, copy(pl.game.time), (pl,), (), repr(e)))
        else:
            output_str = ' --- '.join(
                f'{i.prompt}: {o.output}' for i, o in zip(pl.tasks, pl.results)
            )
            output_info(
                Info(
                    pl.game,
                    copy(pl.game.time),
                    (pl,),
                    (),
                    f'[{pl.role.kind}] ~> {output_str}',
                )
            )
            (info, summary, strategy, *results, remarks) = pl.results
            pl.tasks.clear()
            pl.results = results
            break


async_client = AsyncOpenAI(
    api_key=user_data.api_key,
    base_url=user_data.base_url,
)


async def async_get_console_inputs(pl: PPlayer) -> None:
    pl.results.clear()
    print(f'Major task: {pl.tasks[3].prompt}')
    for i in pl.tasks:
        while True:
            o = await asyncio.to_thread(input, f'{i.prompt}: ')
            if i.options and o not in i.options:
                continue
            pl.results.append(Output(o))


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


async def async_get_ai_inputs(pl: PPlayer) -> None:
    messages: list[ChatCompletionMessageParam] = [
        {'role': 'system', 'content': system_prompt}
    ]
    for info in pl.game.info:
        if pl not in info.target:
            continue
        message: ChatCompletionMessageParam = {
            'role': 'user',
            'content': info.content,
            'name': pls2str(info.source),
        }
        messages.append(message)
    prompt = (
        f'You are seat {pl.seat}, a {pl.role.kind}.\n'
        f'Your personality: {pl.char.description}\n'
        f'Your task: Replace the content in the square brackets with your answer.\n'
        f'Output format: {" --- ".join(str(task) for task in pl.tasks)}'
    )
    messages.append({'role': 'system', 'content': prompt})
    content = await async_input_ai(pl, messages)
    parse(pl, content)


async def async_get_file_inputs(pl: PPlayer) -> None:
    file_path = pathlib.Path(f'io/{pl.seat}.txt')
    prompt = ' --- '.join(str(task) for task in pl.tasks)
    with file_path.open('r', encoding='utf-8') as file:
        lines = file.readlines()
    if not lines or len(lines) < 2:
        raise ValueError('empty file')
    lines[0] = f'{prompt}\n'
    lines[1] = f'Major task: {pl.tasks[3].prompt}\n'
    with file_path.open('w', encoding='utf-8') as file:
        file.writelines(lines)
    while True:
        await asyncio.sleep(1)
        with file_path.open('r', encoding='utf-8') as file:
            lines = file.readlines()
        if not lines:
            raise ValueError('empty file')
        content = lines[0].strip()
        if content == prompt:
            continue
        parse(pl, content)
        lines[0] = f'Please wait...\n'
        with file_path.open('w', encoding='utf-8') as file:
            file.writelines(lines)
        break


async def async_get_inputs(pl: PPlayer) -> None:
    if not pl.tasks:
        raise ValueError('empty task')
    pl.tasks[:0] = [
        Input('your seat, ability, task'),
        Input("summary of the game state and known players' identities"),
        Input('your immediate action and long term strategy'),
    ]
    pl.tasks.append(Input('unpublished annotations'))
    while True:
        try:
            match pl.char.control:
                case 'console':
                    await async_get_console_inputs(pl)
                case 'ai':
                    await async_get_ai_inputs(pl)
                case 'file':
                    await async_get_file_inputs(pl)
                case _:
                    raise NotImplementedError('unknown control')
        except NotImplementedError as e:
            raise
        except Exception as e:
            output_info(Info(pl.game, copy(pl.game.time), (pl,), (), repr(e)))
        else:
            output_str = ' --- '.join(
                f'{i.prompt}: {o.output}' for i, o in zip(pl.tasks, pl.results)
            )
            output_info(
                Info(
                    pl.game,
                    copy(pl.game.time),
                    (pl,),
                    (),
                    f'[{pl.role.kind}] ~> {output_str}',
                )
            )
            (info, summary, strategy, *results, remarks) = pl.results
            pl.tasks.clear()
            pl.results = results
            break
