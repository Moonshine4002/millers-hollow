from openai import OpenAI

from ai import key
from utility import *

client = OpenAI(
    api_key=key.api_key,
    base_url=key.base_url,
)


def get_seat(messages: str) -> str:
    prompt = (
        'You will be given a formatted input describing a game scenario. The format is:\n'
        '[[your life][your name]([your seat])[[your role]]: [[clues]]].\n'
        "Each 'clue' is formatted as: [[[time]][speaker]> [content]].\n\n"
        'Task:\n'
        "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') in the clues.\n"
        '- Answer that question directly.\n\n'
        'Output format:\n'
        '<an integer> reason: <a few sentences explaining your choice>\n'
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


def get_speech(messages: str) -> str:
    prompt = (
        'You will be given a formatted input describing a game scenario. The format is:\n'
        '[[your life][your name]([your seat])[[your role]]: [[clues]]]\n'
        "Each 'clue' is formatted as: [[[time]][speaker]> [content]]\n\n"
        'Task:\n'
        "- Identify the **last question** asked by the Moderator (it will start with 'Moderator>') in the clues.\n"
        '- Compose a response to this question.\n'
        '- Your response will be **broadcast to everyone**, so split your answer into two parts:\n'
        '  1. The speech to be broadcast.\n'
        '  2. The reasoning behind your answer.\n\n'
        'Output format:\n'
        '<speech to everyone> --- reason: <a few sentences explaining your choice>\n'
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
    target = output.split('---')[0].rstrip()
    log(messages, end='\n\n')
    log(output, end='\n\n')
    return target
