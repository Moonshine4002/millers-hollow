from openai import OpenAI

from ai import key
from utility import *

client = OpenAI(
    api_key=key.api_key,
    base_url=key.base_url,
)


def get_seat(messages: str, seat: int, role: str) -> str:
    prompt = (
        "You are playing a game called The Werewolves of Miller's Hollow. "
        'Please be sure that you know the rules. '
        'You will be given a input describing the game scenario.\n'
        f'You are seat {seat}, and your role is {role}.\n\n'
        'Tasks:\n'
        '- Try your best to win the game.\n'
        '- You also win if your teammates win in the end.\n\n'
        'Instructions:\n'
        "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') that asks you to choose a seat.\n"
        "- Choose a seat. It can either benefit or harm the chosen player according to the Moderator's question.\n"
        '- You must not harm yourself unless you are more likely to win by doing that.\n\n'
        'Output format:\n'
        '<number> reason: <reason>\n'
        "(<number> is your chosen seat asked by the Moderator's question. Avoid to output anything before <number>.)\n"
        '(<reason> is a few sentences explaining your choice.)\n'
        '(Your <number> and <reason> should match and make your winning rate higher. Do NOT contradict your <reason> with your <number>.)\n'
        '(Do not keep the words in <> as they are prompts.)\n\n'
    )
    chat_completion = client.chat.completions.create(
        model=key.model,
        messages=[
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': messages},
        ],
    )

    output = chat_completion.choices[0].message.content
    if not output:
        raise ValueError('empty output')
    target = output[0]
    log(messages, end='\n\n')
    log(output, end='\n\n')
    return target


def get_speech(messages: str, seat: int, role: str) -> str:
    prompt = (
        "You are playing a game called The Werewolves of Miller's Hollow. "
        'Please be sure that you know the rules. '
        'You will be given a input describing the game scenario.\n'
        f'You are seat {seat}, and your role is {role}.\n\n'
        'Tasks:\n'
        '- Try your best to win the game.\n'
        '- You also win if your teammates win in the end.\n\n'
        'Instructions:\n'
        "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') where players are asked to speak.\n"
        '- Compose a response to this question.\n'
        '- Your first part of the response will be **broadcast to everyone**, so split your answer into two parts:\n'
        '  1. The speech to be broadcast.\n'
        '  2. The reasoning behind your answer.\n'
        '- You must not harm yourself unless you are more likely to win by doing that.\n\n'
        'Output format:\n'
        '<speech to everyone> --- reason: <a few sentences explaining your choice>\n'
        '(Do not keep the words in <> as they are prompts.)\n'
        '(Avoid to output any newline character.)\n\n'
    )
    chat_completion = client.chat.completions.create(
        model=key.model,
        messages=[
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': messages},
        ],
    )

    output = chat_completion.choices[0].message.content
    if not output:
        raise ValueError('empty output')
    target = output.split('---')[0].rstrip()
    log(messages, end='\n\n')
    log(output, end='\n\n')
    return target
