from openai import OpenAI
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam,
)

from .header import *
from . import user_data


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
    '- The user named "Moderator" will never lie. But anyone else may.\n'
    '- You also win if your teammates win in the end.\n\n'
)


def input_console(pl: PPlayer) -> str:
    return input(f'{pl.seat}> ')


def input_ai(messages: list[ChatCompletionMessageParam]) -> str:
    chat_completion = client.chat.completions.create(
        model=user_data.model,
        messages=messages,
    )
    content = chat_completion.choices[0].message.content
    if not content:
        raise ValueError('empty output')
    return content


def input_file(pl: PPlayer) -> str:
    file_path = pathlib.Path(f'io/{pl.seat}.txt')
    while True:
        time.sleep(1)
        with file_path.open('r', encoding='utf-8') as file:
            lines = file.readlines()
        if not lines:
            continue
        output = lines[0].lstrip('Input:').lstrip().rstrip()
        lines[0] = 'Input: \n'
        with file_path.open('w', encoding='utf-8') as file:
            file.writelines(lines)
        if output:
            return output


def input_control(
    pl: PPlayer, prompt: list[ChatCompletionMessageParam]
) -> str:
    match pl.char.control:
        case 'console':
            return input_console(pl)
        case 'ai':
            return input_ai(prompt)
        case 'file':
            return input_file(pl)
        case _:
            raise NotImplementedError('unknown control')


def parse(pl: PPlayer, content: str) -> str:
    if not DEBUG:
        log(f'{pl.seat}[{pl.role.kind}]~> {content}\n')
        return content.lstrip().rstrip()
    if '---' not in content:
        raise ValueError('wrong format: no "---"')
    lcontent = content.split('---')
    if len(lcontent) != 2:
        raise ValueError('wrong format: more than one "---"')
    reason = lcontent[0].lstrip().rstrip()
    target = lcontent[-1].lstrip().rstrip()
    log(f'{pl.seat}[{pl.role.kind}]~> {target}: {reason}\n')
    return target


def input_middle(
    pl: PPlayer, prompt: str, candidates: list[str] | None = None
) -> str:
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
    messages.append({'role': 'system', 'content': prompt})

    while True:
        try:
            candidate = input_control(pl, messages)
            if pl.char.control == 'ai':
                candidate = parse(pl, candidate)
            if candidates is None:
                return candidate
            if candidate in candidates:
                return candidate
            raise ValueError(f'wrong value: {candidate}')
        except NotImplementedError as e:
            raise
        except Exception as e:
            log(f'{e!r}\n')


def input_word(pl: PPlayer, candidates_iter: Iterable[str]) -> str:
    candidates = list(candidates_iter)
    prompt = (
        f'Your identity: {pl.role.kind}. Your seat {pl.seat}. '
        f'Your task: answer a word in {candidates}.\n'
        'Output format:\n'
        + ('<reason> --- <word>\n' if DEBUG else '<choice>\n')
        + '(E.g. "I don\t know what to say --- pass".)\n'
        '(Keep "---" as separator. Do not keep the words in <> as they are prompts.)\n'
        '(Do not output any newline character.)\n'
        f'(Output using "{user_data.language}".)\n\n'
        f'{user_data.prompt}'
    )
    return input_middle(pl, prompt, candidates)


def input_speech(pl: PPlayer) -> str:
    prompt = (
        f'Your identity: {pl.role.kind}. Your seat {pl.seat}. '
        f'Your task: make a speech.\n'
        'Output format:\n'
        + ('<reason> --- <speech>\n' if DEBUG else '<speech>\n')
        + '(Keep "---" as separator. Do not keep the words in <> as they are prompts.)\n'
        '(Do not output any newline character.)\n'
        f'(Output using "{user_data.language}".)\n\n'
        f'{user_data.prompt}'
    )
    return input_middle(pl, prompt)
