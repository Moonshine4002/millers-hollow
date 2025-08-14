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


class GuiInSkill(BaseModel):
    targets: list[int]
    description: str


class GuiInput(BaseModel):
    model: str
    me: str
    players: str
    skills: dict[str, GuiInSkill]
    log: str


class GuiOutput(BaseModel):
    skill: str
    target: int
    speech: str
    reason: str


json_format = """\
{
    "reason": "Your reasoning (which will not be public to any player): \
analyze the current situation, infer player identities and credibility, \
explain strategy choices, predict potential risks..."
    "skill": "Your chosen skill",
    "target": An integer seat number if needed (input 0 if ignored),
    "speech": "Public or private according to the skill (input "" if ignored)",
}\
"""

frame = """\
You are playing a game called The Werewolves of Miller's Hollow.
Please be sure that you know the rules.
You will be given a input describing the game scenario.
Try your best to win the game.
Game rules:
- The Moderator is always truthful.
- You win if your team wins. Always act in the best interests of your team.
- Werewolves win by eliminating either all villagers or all gods.
- The identity of the deceased players remain hidden.
- Players killed on the first night or eliminated by vote have a dying speech.
Tips:
- Avoid repetitive or meaningless statements.
- You can reveal your true identity, conceal it, \
or impersonate another role—regardless of your faction.
- Not all information is public, discussing these may expose your identity.
Output format:
- Output using "{language}".
- Please reply strictly according to this JSON format:
{json_format}
Your info:
{me}
Players info: information extracted from the game log that might be outdated.
{players}
Available skills: choose only one, but if they are not contradictory, \
you may be able to use the others simultaneously in the next question.
{skills}
Game log:
{log}\
"""


async def input_ai(input_: GuiInput) -> GuiOutput:
    formated = frame.format(
        language=language,
        json_format=json_format,
        me=input_.me,
        players=input_.players,
        skills=skill_text(input_),
        log=input_.log,
    )
    messages: list[ChatCompletionMessageParam] = []
    messages.append({'role': 'user', 'content': formated})
    errors = 0
    while True:
        chat_completion = await async_client.chat.completions.create(
            messages=messages,
            model=input_.model,
        )
        content = chat_completion.choices[0].message.content
        try:
            if not content:
                content = ''
                raise ValueError('empty output')
            output = parse(content)
            logic(output, input_)
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


def skill_text(input_: GuiInput) -> str:
    return '\n'.join(
        f'\tSkill name: {skill}; Skill description: {skill_model.description}; Target options: {skill_model.targets}'
        for skill, skill_model in input_.skills.items()
    )


def parse(content: str) -> GuiOutput:
    matches: list[str] = re.findall(r'\{.*\}', content, re.DOTALL)
    if len(matches) != 1:
        raise ValueError(f'Got {len(matches)} matches')
    return GuiOutput.model_validate_json(matches[0])


def logic(output: GuiOutput, input_: GuiInput) -> None:
    skills = list(input_.skills.keys())
    if output.skill not in skills:
        raise ValueError(f'Invalid JSON format: chosen skill beyond {skills}')
    targets = input_.skills[output.skill].targets
    if output.target not in targets:
        raise ValueError(f'Invalid JSON format: chosen target beyond {targets}')
