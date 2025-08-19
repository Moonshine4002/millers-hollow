import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, RootModel, model_validator

from .config import config

language = config.get('ai', 'language')


class InputDialogue(BaseModel):
    type: Literal['dialogue']
    name: str
    description: str


class InputSeat(BaseModel):
    type: Literal['seat']
    name: str
    description: str
    options: list[int]


class InputWord(BaseModel):
    type: Literal['word']
    name: str
    description: str
    options: list[str]


SkillType = Annotated[InputDialogue | InputSeat | InputWord, Field(discriminator='type')]


class InputSkill(BaseModel):
    controller: str
    model: str
    prompt: dict[str, str]
    skills: list[SkillType]


class OutputDialogue(BaseModel):
    type: Literal['dialogue']
    name: str
    dialogue: str
    reason: str


class OutputSeat(BaseModel):
    type: Literal['seat']
    name: str
    seat: int
    reason: str


class OutputWord(BaseModel):
    type: Literal['word']
    name: str
    word: str
    reason: str


ActionType = Annotated[
    OutputDialogue | OutputSeat | OutputWord, Field(discriminator='type')
]


class OutputSkill(RootModel):
    root: ActionType


class IOValidator(BaseModel):
    input_: InputSkill
    output: OutputSkill

    @model_validator(mode='after')
    def validator(self) -> Self:
        skills_map = {s.name: s for s in self.input_.skills}

        output_skill = self.output.root

        if self.input_.controller == 'ai' and not output_skill.reason.strip():
            raise ValueError(f'Reason cannot be empty')

        skill_name = output_skill.name
        if skill_name not in skills_map:
            raise ValueError(
                f"Invalid skill '{skill_name}', allowed: {list(skills_map.keys())}"
            )

        input_skill = skills_map[skill_name]

        if isinstance(output_skill, OutputDialogue) and isinstance(
            input_skill, InputDialogue
        ):
            if not output_skill.dialogue.strip():
                raise ValueError(f"Dialogue cannot be empty for skill '{skill_name}'")
        elif isinstance(output_skill, OutputSeat) and isinstance(input_skill, InputSeat):
            if output_skill.seat not in input_skill.options:
                raise ValueError(
                    f"Invalid seat '{output_skill.seat}' for skill '{skill_name}', "
                    f'allowed: {input_skill.options}'
                )
        elif isinstance(output_skill, OutputWord) and isinstance(input_skill, InputWord):
            if output_skill.word not in input_skill.options:
                raise ValueError(
                    f"Invalid word '{output_skill.word}' for skill '{skill_name}', "
                    f'allowed: {input_skill.options}'
                )
        else:
            raise RuntimeError('Wrong IO type')

        return self


info_frame = """\
Your info:
{player}
Players info:
{players}
Game log:
{log}
Available skills:
{skills}\
"""
json = """\
- Please choose one of the following JSON formats and reply strictly according to it:
    {
        "reason": str,
        "type": Literal["dialogue"],
        "name": str,
        "dialogue": str,
    }
    {
        "reason": str,
        "type": Literal["seat"],
        "name": str,
        "seat": int,
    }
    {
        "reason": str,
        "type": Literal["word"],
        "name": str,
        "word": str,
    }
    Description of all fields:
        reason: Your reasoning (which will not be public to any player): \
    analyze the current situation, infer player identities and credibility, \
    explain strategy choices, predict potential risks...
        type: do not change this field
        name: Your chosen skill name in "available skills".
        dialogue: Public or private according to the skill.
        seat: An integer seat number (input 0 as PASS).
        word: A string, your choice.\
"""
prompt_frame = """\
You are playing a game called The Werewolves of Miller's Hollow.
Please be sure that you know the rules.
You will be given a input describing the game scenario.
Try to behave as much like a human as possible.
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
{info}
Output format:
- Output using "{language}".
- Choose only one skill from all available skills, but if they are not contradictory, \
you may be able to choose the others simultaneously in the next question.
{json}\
"""


def parse(input_: InputSkill, content: str) -> OutputSkill:
    matches: list[str] = re.findall(r'\{.*\}', content, re.DOTALL)
    if len(matches) != 1:
        raise ValueError(f'Got {len(matches)} matches')
    output = OutputSkill.model_validate_json(matches[0])
    IOValidator(input_=input_, output=output)
    return output


def get_skill_text(skills: list[SkillType]) -> str:
    skills_list: list[str] = []
    for skill in skills:
        if isinstance(skill, InputDialogue):
            skills_list.append(
                f'\tSkill type: dialogue; Skill name: {skill.name}; Skill description: {skill.description}'
            )
        elif isinstance(skill, InputSeat):
            skills_list.append(
                f'\tSkill type: seat; Skill name: {skill.name}; Skill description: {skill.description}; Options: {skill.options}'
            )
        elif isinstance(skill, InputWord):
            skills_list.append(
                f'\tSkill type: word; Skill name: {skill.name}; Skill description: {skill.description}; Options: {skill.options}'
            )
    return '\n'.join(skills_list)


def get_input(
    controller: str,
    model: str,
    player: str,
    players: str,
    log: str,
    skills: list[SkillType],
) -> InputSkill:
    skills_text = get_skill_text(skills)
    info = info_frame.format(player=player, players=players, log=log, skills=skills_text)
    prompt = {
        'prompt': prompt_frame.format(info=info, language=language, json=json),
        'skills': skills_text,
    }
    return InputSkill(controller=controller, model=model, prompt=prompt, skills=skills)
