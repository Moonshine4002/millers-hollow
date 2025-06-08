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
    f'{user_data.additional_prompt}'
)


class Input(NamedTuple):
    prompt: str
    options: list[str] = []

    def __str__(self) -> str:
        options = f' in one of {self.options}' if self.options else ''
        return f'[{self.prompt}]{options}'


class Output(NamedTuple):
    output: str


def output(
    pls_iter: Iterable[PPlayer],
    clue: Clue,
    system: bool = False,
    clear_text: str = '',
) -> None:
    pls = list(pls_iter)
    log(f'{clue} > {pls2str(pls)}\n', clear_text=clear_text)
    if system or any(pl.char.control == 'console' for pl in pls):
        print(str(clue))
    for pl in pls:
        if pl.char.control != 'file':
            continue
        file_path = pathlib.Path(f'io/{pl.seat}.txt')
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if clear_text:
            file_path.write_text(clear_text, encoding='utf-8')
        with file_path.open(mode='a', encoding='utf-8') as file:
            file.write(f'{clue}\n')


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


def get_console_inputs(pl: PPlayer, inputs: Iterable[Input]) -> list[Output]:
    outputs: list[Output] = []
    for i in inputs:
        outputs.append(Output(input(f'{i.prompt}: ')))
    return outputs


def get_ai_inputs(pl: PPlayer, inputs_iter: Iterable[Input]) -> str:
    inputs = list(inputs_iter)
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
    prompt = f'You are seat {pl.seat}, a {pl.role.kind}.\n' 'Output format: '
    prompt += ' --- '.join(str(i) for i in inputs)
    messages.append({'role': 'system', 'content': prompt})
    return input_ai(pl, messages)


def get_file_inputs(pl: PPlayer) -> str:
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


def parse(
    pl: PPlayer, inputs_iter: Iterable[Input], content: str
) -> list[Output]:
    inputs = list(inputs_iter)
    content = content.replace('\n', ' ')
    if len(inputs) == 1:
        lcontent = [content]
    else:
        if '---' not in content:
            raise ValueError(f'wrong format: 0 "---"')
        lcontent = content.split('---')
        if len(lcontent) != len(inputs):
            raise ValueError(f'wrong format: {len(lcontent) - 1} "---"')
    outputs = [Output(content.strip(' "[]')) for content in lcontent]
    for i, o in zip(inputs, outputs):
        if i.options and o.output not in i.options:
            raise ValueError(f'wrong value: {o.output}')
    return outputs


def get_inputs(pl: PPlayer, inputs: Iterable[Input]) -> list[Output]:
    while True:
        try:
            match pl.char.control:
                case 'console':
                    outputs = get_console_inputs(pl, inputs)
                case 'ai':
                    content = get_ai_inputs(pl, inputs)
                    outputs = parse(pl, inputs, content)
                case 'file':
                    content = input_file(pl)
                    outputs = parse(pl, inputs, content)
                case _:
                    raise NotImplementedError('unknown control')
            break
        except NotImplementedError as e:
            raise
        except Exception as e:
            log(f'{e!r}\n')
    output_str = ' --- '.join(
        f'{i.prompt}: {o.output}' for i, o in zip(inputs, outputs)
    )
    log(f'{pl.seat}[{pl.role.kind}]~> {output_str}\n')
    return outputs


def input_word(pl: PPlayer, candidates_iter: Iterable[str]) -> str:
    thought, choice = get_inputs(
        pl,
        (Input('your thought'), Input('your choice', list(candidates_iter))),
    )
    return choice.output


def input_speech(pl: PPlayer) -> str:
    thought, speech = get_inputs(
        pl, (Input('your thought'), Input('your speech'))
    )
    return speech.output
