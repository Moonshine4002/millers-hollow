from openai import OpenAI
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
    '- Output must be in one line without newlines.\n'
    f'- Output using "{user_data.language}".\n\n'
    'Game rules:\n'
    f'- Werewolves win by eliminating {user_data.win_condition} villagers.\n'
    f"- Werewolves {'can' if user_data.allow_exposure else 'can not'} expose themselves."
    f'- The sheriff election continues for {user_data.election_round} rounds.\n'
    '- Players killed on the first night or eliminated by vote have a dying speech.\n'
    "- The seer's verification only reveals whether the target belongs to the good faction, not their specific role.\n"
    '- The witch cannot use the antidote to save herself after the first night.\n'
    '- The player cannot use any skills after poisoned by the witch.\n'
    '- The guard cannot protect the same player for two consecutive nights.\n'
    '- Simultaneous protection by the witch and guard on the same target has no effect.\n\n'
    'Tips:\n'
    "- Avoid repeating others' statements.\n"
    '- You can reveal your true role or impersonate another role (regardless of your faction).\n'
    '- When impersonating, fully develop your thought process and reasoning.\n\n'
)


def input_console(pl: PPlayer) -> str:
    return input(f'{pl.seat}> ')


def input_ai(pl: PPlayer, messages: list[ChatCompletionMessageParam]) -> str:
    chat_completion = client.chat.completions.create(
        model=pl.char.model,
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
        output = lines[0].lstrip('Input:').strip()
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
            return input_ai(pl, prompt)
        case 'file':
            return input_file(pl)
        case _:
            raise NotImplementedError('unknown control')


def parse(pl: PPlayer, content: str) -> str:
    if not DEBUG:
        content = content.replace('\n', '').strip(' "[]')
        log(f'{pl.seat}[{pl.role.kind}]~> {content}\n')
        return content
    if '---' not in content:
        raise ValueError('wrong format: no "---"')
    lcontent = content.split('---')
    if len(lcontent) != 2:
        raise ValueError('wrong format: more than one "---"')
    reason = lcontent[0].replace('\n', '').strip(' "[]')
    target = lcontent[1].replace('\n', '').strip(' "[]')
    log(f'{pl.seat}[{pl.role.kind}]~> {target} --- {reason}\n')
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
            if not candidates:
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
        f'Role: {pl.role.kind}. Seat: {pl.seat}. '
        f"Task: {'your thought, followed by' if DEBUG else 'choose'} one option in {candidates}.\n"
        'Output format:\n'
        f"{'[Your thought] --- 'if DEBUG else ''}[Selected option]\n"
        f'{user_data.additional_prompt}'
    )
    return input_middle(pl, prompt, candidates)


def input_speech(pl: PPlayer) -> str:
    prompt = (
        f'Role: {pl.role.kind}. Seat: {pl.seat}. '
        f"Task: {'your thought, followed by' if DEBUG else 'make'} a speech.\n"
        'Output format:\n'
        f"{'[Your thought] --- 'if DEBUG else ''}[Speech content]\n"
        f'{user_data.additional_prompt}'
    )
    return input_middle(pl, prompt)
