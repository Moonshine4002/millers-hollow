from configparser import ConfigParser
import re

from openai import OpenAI, AsyncOpenAI
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam,
)
from pydantic import BaseModel

config = ConfigParser()
config.read('./config.ini', encoding='utf-8')

api_key = config.get('ai', 'api_key')
base_url = config.get('ai', 'base_url')
language = config.get('ai', 'language')


client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)

async_client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url,
)


class JsonFormat(BaseModel):
    skill: str
    target: int
    speech: str
    reason: str


json_format = """
{
    "skill": "Your chosen skill",
    "target": An integer seat number if needed (input 0 if ignored),
    "speech": "Public or private according to the skill (input "" if ignored)",
    "reason": "Your reasoning (which will not be public)"
}
"""

frame = """
You are playing a game called The Werewolves of Miller's Hollow.
Please be sure that you know the rules.
You will be given a input describing the game scenario.
Try your best to win the game.
Game rules:
- The Moderator is always truthful.
- You win if your team wins.
- Werewolves win by eliminating either all villagers or all gods.
- Werewolves can suicidally expose themselves, ending that day instantly."
- The sheriff election continues for 2 rounds.
- Players killed on the first night or eliminated by vote have a dying speech.
Output format:
- Output using "{language}".
- Please reply strictly according to this JSON format:
{json_format}
Your info:
{me}
Players:
{players}
Available skills:
{skills}
Valid targets:
{targets}
Game log:
{log}
"""


async def input_ai(
    model: str,
    me: str,
    players: str,
    skills: list[str],
    targets: list[int],
    log: str,
) -> JsonFormat:
    input_ = frame.format(
        language=language,
        json_format=json_format,
        me=me,
        players=players,
        skills=skills,
        targets=targets,
        log=log,
    )
    messages: list[ChatCompletionMessageParam] = []
    messages.append({'role': 'user', 'content': input_})
    errors = 0
    while True:
        chat_completion = await async_client.chat.completions.create(
            messages=messages,
            model=model,
        )
        content = chat_completion.choices[0].message.content
        try:
            if not content:
                content = ''
                raise ValueError('empty output')
            output = parse(content)
            logic(output, skills, targets)
        except Exception as e:
            errors += 1
            if errors > 3:
                raise
            print(f'Error: {e}')
            messages.append({'role': 'assistant', 'content': content})
            messages.append(
                {
                    'role': 'system',
                    'content': f'You output in wrong format, error: {e}',
                }
            )
        else:
            break
    return output


def parse(content: str) -> JsonFormat:
    matches: list[str] = re.findall(r'\{.*\}', content, re.DOTALL)
    if len(matches) != 1:
        raise ValueError(f'Got {len(matches)} matches')
    return JsonFormat.model_validate_json(matches[0])


def logic(output: JsonFormat, skills: list[str], targets: list[int]) -> None:
    if output.skill not in skills:
        raise ValueError(f'Invalid JSON format: chosen skill beyond {skills}')
    if output.target not in targets:
        raise ValueError(f'Invalid JSON format: chosen target beyond {targets}')
