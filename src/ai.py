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


def input_console(prompt: str) -> str:
    return input(prompt)


def input_ai(player: PPlayer, **prompts: str) -> list[str]:
    prompt = (
        "You are playing a game called The Werewolves of Miller's Hollow. "
        'Please be sure that you know the rules. '
        'You will be given a input describing the game scenario.\n\n'
        'Your identity:\n'
        f'You are seat {player.role.seat}, and your role is {player.role.role}.\n\n'
        'Objectives:\n'
        '- Try your best to win the game.\n'
        '- You also win if your teammates win in the end.\n'
        '- You must not harm yourself or your teammates unless you are more likely to win by doing that.\n\n'
        'Instructions:\n'
        '- Identify the **last question** asked by the Moderator (a user).\n'
        "- The Moderator (a user) won't lie. But anyone else may.\n"
        f"{prompts['instructions']}"
        f'{user_data.prompt}'
        'Output format:\n'
        f"{prompts['format']}"
        '(Keep "---" as separator. Do not keep the words in <> as they are prompts.)\n'
        '(Do not output any newline character.)\n'
        f'(Output using "{user_data.language}".)\n\n'
    )
    messages: list[ChatCompletionMessageParam] = [
        {'role': 'system', 'content': prompt},
    ]
    for clue in player.clues:
        d: ChatCompletionMessageParam = {
            'role': 'user',
            'content': clue.clue,
            'name': clue.source,
        }
        # if clue.source == 'Moderator':
        #    d['role'] = 'system'
        messages.append(d)

    chat_completion = client.chat.completions.create(
        model=user_data.model,
        messages=messages,
    )
    output = chat_completion.choices[0].message.content
    if not output:
        raise ValueError('empty output')
    if DEBUG:
        if '---' not in output:
            raise ValueError('wrong format: no "---"')
        output_split = output.split('---')
        if len(output_split) != 2:
            raise ValueError('wrong format: more than one "---"')
        reason = output_split[0].lstrip().rstrip()
        target = output_split[-1].lstrip().rstrip()
        return [reason, target]
    else:
        return [output.lstrip().rstrip()]


def input_file(player: PPlayer) -> str:
    file_path = pathlib.Path(f'io/{player.role.seat}.txt')
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


def get(
    player: PPlayer, condition: Callable[[str], bool], **prompts: str
) -> str:
    while True:
        try:
            match player.character.control:
                case 'console':
                    candidate = input_console(f'{player.role.seat}> ')
                    if not condition(candidate):
                        raise ValueError(f'wrong value: {candidate}')
                    return candidate
                case 'ai':
                    if DEBUG:
                        reason, candidate = input_ai(player, **prompts)
                    else:
                        candidate = input_ai(player, **prompts)[0]
                    if not condition(candidate):
                        raise ValueError(f'wrong value: {candidate}')
                    if DEBUG:
                        log(
                            f'{player.role.seat}[{player.role.role}]~> {candidate}: {reason}\n'
                        )
                    else:
                        log(
                            f'{player.role.seat}[{player.role.role}]~> {candidate}\n'
                        )
                    return candidate
                case 'file':
                    candidate = input_file(player)
                    if not condition(candidate):
                        raise ValueError(f'wrong value: {candidate}')
                    return candidate
                case _:
                    raise NotImplementedError('unknown control')
        except NotImplementedError as e:
            raise
        except Exception as e:
            log(f'{e!r}\n')


def get_seat(player: PPlayer, candidates: Sequence[Seat]) -> Seat:
    prompts = {
        'instructions': "- Choose a seat. It can either benefit or harm the chosen player according to the Moderator's question.\n",
        'format': 'Reason: <reason> --- <number>\n'
        "(<number> is your chosen seat asked by the Moderator's question. You MUST only output the number.)\n"
        '(<reason> is a few sentences explaining your choice.)\n',
    }
    if not DEBUG:
        prompts['format'] = '<number>\n'

    def condition(output: str) -> bool:
        seat = Seat(output)
        if seat not in candidates:
            return False
        return True

    seat = get(player, condition, **prompts)
    return Seat(seat)


def get_word(player: PPlayer, candidates: Sequence[str]) -> str:
    prompts = {
        'instructions': "- Answer a word. It can either benefit or harm the chosen player according to the Moderator's question.\n",
        'format': 'Reason: <reason> --- <word>\n'
        "(<word> is your reply of the Moderator's question. You MUST only output a word within the choices given by the Moderator.)\n"
        '(<reason> is a few sentences explaining your choice.)\n',
    }
    if not DEBUG:
        prompts['format'] = '<word>\n'

    def condition(output: str) -> bool:
        if output not in candidates:
            return False
        return True

    candidate = get(player, condition, **prompts)
    return candidate


def get_speech(player: PPlayer) -> str:
    prompts = {
        'instructions': "- Compose a response to the Moderator's question.\n"
        "- Your second part of the response will be broadcast (audiences depend on the Moderator's question), so split your answer into two parts:\n"
        '  1. The reasoning behind your speech.\n'
        '  2. The speech to be broadcast.\n',
        'format': 'Reason: <a few sentences explaining your choice> --- <speech to be broadcast>\n',
    }
    if not DEBUG:
        prompts['instructions'] = '- Compose a speech to be broadcast.\n'
        prompts['format'] = '<speech to be broadcast>\n'

    def condition(output: str) -> bool:
        return True

    candidate = get(player, condition, **prompts)
    return candidate
