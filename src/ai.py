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


def output(player: PPlayer, content: str) -> None:
    match player.character.control:
        case 'console':
            print(content)
        case 'ai':
            pass
        case 'gui':
            pass
        case _:
            raise NotImplementedError('unknown control')


def input_console(prompt: str) -> str:
    return input(prompt)


def input_ai(player: PPlayer, **prompts: str) -> tuple[str, str]:
    prompt = (
        "You are playing a game called The Werewolves of Miller's Hollow. "
        'Please be sure that you know the rules. '
        'You will be given a input describing the game scenario.\n'
        f'You are seat {player.role.seat}, and your role is {player.role.role}.\n\n'
        'Tasks:\n'
        '- Try your best to win the game.\n'
        '- You also win if your teammates win in the end.\n\n'
        'Instructions:\n'
        f"{prompts['instructions']}"
        'Output format:\n'
        f"{prompts['format']}"
        '(Do not keep the words in <> as they are prompts.)\n'
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
    if '---' not in output:
        raise ValueError('wrong format')
    output_split = output.split('---')
    if len(output_split) != 2:
        raise ValueError('wrong format')
    reason = output_split[0].lstrip().rstrip()
    target = output_split[-1].lstrip().rstrip()
    return reason, target


def input_gui(prompt: str) -> str:
    return input(prompt)


def get(
    player: PPlayer, condition: Callable[[str], bool], **prompts: str
) -> str:
    while True:
        try:
            match player.character.control:
                case 'console':
                    candidate = input_console(f'{player.role.seat}> ')
                    if not condition(candidate):
                        raise ValueError('wrong value')
                    return candidate
                case 'ai':
                    reason, candidate = input_ai(player, **prompts)
                    if not condition(candidate):
                        raise ValueError('wrong value')
                    log(
                        f'{player.role.seat}[{player.role.role}]~> {candidate}: {reason}'
                    )
                    return candidate
                case 'gui':
                    pass
                case _:
                    raise NotImplementedError('unknown control')
        except NotImplementedError as e:
            raise
        except Exception as e:
            log(str(e))


def get_seat(player: PPlayer, candidates: Sequence[Seat]) -> Seat:
    prompts = {
        'instructions': "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') that asks you to choose a seat.\n"
        "- Choose a seat. It can either benefit or harm the chosen player according to the Moderator's question.\n"
        '- You must not harm yourself or your teammates unless you are more likely to win by doing that.\n\n',
        'format': 'Reason: <reason> --- <number>\n'
        "(<number> is your chosen seat asked by the Moderator's question. You MUST only output the number.)\n"
        '(<reason> is a few sentences explaining your choice.)\n',
    }

    def condition(output: str) -> bool:
        seat = Seat(output)
        if seat not in candidates:
            return False
        return True

    seat = get(player, condition, **prompts)
    return Seat(seat)


def get_word(player: PPlayer, candidates: Sequence[str]) -> str:
    prompts = {
        'instructions': "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') that asks you to reply a word.\n"
        "- Answer the question. It can either benefit or harm the chosen player according to the Moderator's question.\n"
        '- You must not harm yourself or your teammates unless you are more likely to win by doing that.\n\n',
        'format': 'Reason: <reason> --- <word>\n'
        "(<word> is your reply of the Moderator's question. You MUST only output a word within the choices given by the Moderator.)\n"
        '(<reason> is a few sentences explaining your choice.)\n',
    }

    def condition(output: str) -> bool:
        if output not in candidates:
            return False
        return True

    candidate = get(player, condition, **prompts)
    return candidate


def get_speech(player: PPlayer) -> str:
    prompts = {
        'instructions': "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') where players are asked to speak.\n"
        '- Compose a response to this question.\n'
        '- Your second part of the response will be **broadcast to everyone**, so split your answer into two parts:\n'
        '  1. The reasoning behind your speech.\n'
        '  2. The speech to be broadcast.\n'
        '- You must not harm yourself or your teammates unless you are more likely to win by doing that.\n\n',
        'format': 'Reason: <a few sentences explaining your choice> --- <speech to everyone>\n',
    }

    def condition(output: str) -> bool:
        return True

    candidate = get(player, condition, **prompts)
    return candidate
