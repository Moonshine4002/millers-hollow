from openai import OpenAI, AsyncOpenAI
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from ..common.config import config
from ..common.io import InputSkill, OutputSkill, parse
from ..common.log import log

api_key = config.get('ai', 'api_key')
base_url = config.get('ai', 'base_url')

client = OpenAI(api_key=api_key, base_url=base_url)
async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)


async def input_ai(input_: InputSkill) -> OutputSkill:
    prompt = input_.prompt['prompt']
    messages: list[ChatCompletionMessageParam] = []
    messages.append({'role': 'user', 'content': prompt})
    log(prompt)
    errors = 0
    while True:
        chat_completion = await async_client.chat.completions.create(
            messages=messages, model=input_.model
        )
        content = chat_completion.choices[0].message.content
        try:
            if not content:
                raise ValueError('empty output')
            output = parse(input_, content)
        except Exception as e:
            errors += 1
            if errors == 3:
                raise
            log(f'Error: {e}')
            messages.append({'role': 'assistant', 'content': content})
            messages.append(
                {'role': 'system', 'content': f'You output in wrong format, error: {e}'}
            )
        else:
            log(content)
            break
    return output
