from openai import OpenAI

from ai import key

client = OpenAI(
    api_key=key.api_key,
    base_url=key.base_url,
)


def get_seat(messages: str) -> str:
    prompt = (
        'The info given by the user is formatted as [[your life][your name]([your seat])[[your role]]: [[clues]]]. '
        'The clue, component of the "clues", is formatted as [[[time]][speaker]> [content]]. '
        'Please answer the last question in the "clues" asked by the Moderator (starting with "Moderator> ") '
        'Your answer format: [[a integer] reason: [a few sentences]], do not output any brackets.\n'
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
    print(prompt + messages)
    print(output)
    return target


def get_speech(messages: str) -> str:
    prompt = (
        'The info given by the user is formatted as [[your life][your name]([your seat])[[your role]]: [[clues]]]. '
        'The clue, component of the "clues", is formatted as [[[time]][speaker]> [content]]. '
        'Please answer the last question in the "clues" asked by the Moderator (starting with "Moderator> ") '
        'Your answer format: [[a few sentences] --- reason: [a few sentences]], do not output any brackets. '
        'Please be aware that your speech ahead of the "---" are boardcast to everyone.\n'
    )
    chat_completion = client.chat.completions.create(
        model='glm-4',
        messages=[
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': messages},
        ],
    )

    output = chat_completion.choices[0].message.content
    if not output:
        raise ValueError('empty output')
    target = output.split('---')[0].rstrip()
    print(prompt + messages)
    print(output)
    return target
