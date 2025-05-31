from openai import OpenAI

from ..header import *
from . import key

client = OpenAI(
    api_key=key.api_key,
    base_url=key.base_url,
)


def control_input(prompt: str) -> str:
    return input(prompt)


def control_ai(prompt: str, message: str) -> tuple[str, str]:
    chat_completion = client.chat.completions.create(
        model=key.model,
        messages=[
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': message},
        ],
    )
    output = chat_completion.choices[0].message.content
    if not output:
        raise ValueError('empty output')
    if '---' not in output:
        raise ValueError('wrong format')
    output_split = output.split('---')
    if len(output_split) != 2:
        raise ValueError('wrong format')
    reason = output_split[0].lstrip().rstrip()
    target = output_split[-1].lstrip().rstrip()
    return reason, target


def get_seat(player: PPlayer, candidates: Sequence[Seat]) -> Seat:
    prompt = (
        "You are playing a game called The Werewolves of Miller's Hollow. "
        'Please be sure that you know the rules. '
        'You will be given a input describing the game scenario.\n'
        f'You are seat {player.role.seat}, and your role is {player.role.role}.\n\n'
        'Tasks:\n'
        '- Try your best to win the game.\n'
        '- You also win if your teammates win in the end.\n\n'
        'Instructions:\n'
        "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') that asks you to choose a seat.\n"
        "- Choose a seat. It can either benefit or harm the chosen player according to the Moderator's question.\n"
        '- You must not harm yourself or your teammates unless you are more likely to win by doing that.\n\n'
        'Output format:\n'
        'Reason: <reason> --- <number>\n'
        "(<number> is your chosen seat asked by the Moderator's question. You MUST only output the number.)\n"
        '(<reason> is a few sentences explaining your choice.)\n'
        '(Do not keep the words in <> as they are prompts.)\n'
        '(Do not output any newline character.)\n\n'
    )
    message = player.text_clues()

    match player.character.control:
        case 'input':
            while True:
                try:
                    target = control_input(f'{player.role.seat}> ')
                    candidate = Seat(target)
                    if candidate in candidates:
                        return candidate
                except Exception as e:
                    pass
        case 'ai':
            while True:
                try:
                    reason, target = control_ai(prompt, message)
                    candidate = Seat(target)
                    if candidate in candidates:
                        log(
                            f'{player.role.seat}[{player.role.role}]~> {candidate}: {reason}'
                        )
                        return candidate
                except Exception as e:
                    log(str(e))
        case _:
            raise NotImplementedError('unknown control')


def get_word(player: PPlayer, candidates: Sequence[str]) -> str:
    prompt = (
        "You are playing a game called The Werewolves of Miller's Hollow. "
        'Please be sure that you know the rules. '
        'You will be given a input describing the game scenario.\n'
        f'You are seat {player.role.seat}, and your role is {player.role.role}.\n\n'
        'Tasks:\n'
        '- Try your best to win the game.\n'
        '- You also win if your teammates win in the end.\n\n'
        'Instructions:\n'
        "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') that asks you to reply a word.\n"
        "- Answer the question. It can either benefit or harm the chosen player according to the Moderator's question.\n"
        '- You must not harm yourself or your teammates unless you are more likely to win by doing that.\n\n'
        'Output format:\n'
        'Reason: <reason> --- <word>\n'
        "(<word> is your reply of the Moderator's question. You MUST only output a word within the choices given by the Moderator.)\n"
        '(<reason> is a few sentences explaining your choice.)\n'
        '(Do not keep the words in <> as they are prompts.)\n'
        '(Do not output any newline character.)\n\n'
    )
    message = player.text_clues()

    match player.character.control:
        case 'input':
            while True:
                try:
                    target = control_input(f'{player.role.seat}> ')
                    candidate = target
                    if candidate in candidates:
                        return candidate
                except Exception as e:
                    pass
        case 'ai':
            while True:
                try:
                    reason, target = control_ai(prompt, message)
                    candidate = target
                    if candidate in candidates:
                        log(
                            f'{player.role.seat}[{player.role.role}]~> {candidate}: {reason}'
                        )
                        return candidate
                except Exception as e:
                    log(str(e))
        case _:
            raise NotImplementedError('unknown control')


def get_speech(player: PPlayer) -> str:
    prompt = (
        "You are playing a game called The Werewolves of Miller's Hollow. "
        'Please be sure that you know the rules. '
        'You will be given a input describing the game scenario.\n'
        f'You are seat {player.role.seat}, and your role is {player.role.role}.\n\n'
        'Tasks:\n'
        '- Try your best to win the game.\n'
        '- You also win if your teammates win in the end.\n\n'
        'Instructions:\n'
        "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') where players are asked to speak.\n"
        '- Compose a response to this question.\n'
        '- Your second part of the response will be **broadcast to everyone**, so split your answer into two parts:\n'
        '  1. The reasoning behind your speech.\n'
        '  2. The speech to be broadcast.\n'
        '- You must not harm yourself or your teammates unless you are more likely to win by doing that.\n\n'
        'Output format:\n'
        'Reason: <a few sentences explaining your choice> --- <speech to everyone>\n'
        '(Do not keep the words in <> as they are prompts.)\n'
        '(Do not output any newline character.)\n\n'
    )
    message = player.text_clues()

    match player.character.control:
        case 'input':
            while True:
                try:
                    target = control_input(f'{player.role.seat}> ')
                    candidate = target
                    if True:
                        return candidate
                except Exception as e:
                    pass
        case 'ai':
            while True:
                try:
                    reason, target = control_ai(prompt, message)
                    candidate = target
                    if True:
                        log(
                            f'{player.role.seat}[{player.role.role}]~> {reason}'
                        )
                        return candidate
                except Exception as e:
                    log(str(e))
        case _:
            raise NotImplementedError('unknown control')
