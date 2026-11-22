from pathlib import Path
from typing import TypeVar

import yaml
from litellm import Router
from pydantic import BaseModel

from millers_hollow.core.bus import Output, OutputBus

BaseModelT = TypeVar('BaseModelT', bound=BaseModel)


class LLM:
    def __init__(self) -> None:
        self.config = self.load_config()
        self.router = Router(self.config['model_list'])

    @staticmethod
    def load_config(path: Path = Path('config.yaml')) -> dict:
        with path.open(encoding='utf-8') as f:
            return yaml.safe_load(f)

    async def stream_chat(self, model: str, prompt: str, bus: OutputBus) -> str:
        response = await self.router.acompletion(
            model, [{'role': 'user', 'content': prompt}], stream=True
        )
        reasoning_buffer: list[str] = []
        content_buffer: list[str] = []
        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning = getattr(delta, 'reasoning_content', None)
            content = getattr(delta, 'content', None)
            if reasoning:
                reasoning_buffer.append(reasoning)
                bus.publish(Output(reasoning, 'reasoning', stream=True))
            if content:
                content_buffer.append(content)
                bus.publish(Output(content, 'content', stream=True))
        if reasoning_buffer:
            bus.publish(Output('', 'reasoning', stream=True, end=True))
            reasoning = ''.join(reasoning_buffer)  # TODO: support reasoning output
            bus.publish(Output(reasoning, 'reasoning'))
        if content_buffer:
            bus.publish(Output('', 'content', stream=True, end=True))
            content = ''.join(content_buffer)
            bus.publish(Output(content, 'content'))
            return content
        raise ValueError('LLM returned empty content')

    async def structured_chat(
        self, model: str, prompt: str, validation: type[BaseModelT], bus: OutputBus
    ) -> BaseModelT:
        response = await self.router.acompletion(
            model, [{'role': 'user', 'content': prompt}], response_format=validation
        )  # TODO: support streaming
        content = response.choices[0].message.content
        if content is None:
            raise ValueError('LLM returned empty content')
        bus.publish(Output(content, 'summary'))
        return validation.model_validate_json(content)

    async def structured_stream_chat(
        self,
        stream_model: str,
        stream_prompt: str,
        structured_model: str,
        structured_prompt: str,
        validation: type[BaseModelT],
        bus: OutputBus,
    ) -> BaseModelT:
        content = await self.stream_chat(stream_model, stream_prompt, bus)
        return await self.structured_chat(
            structured_model, structured_prompt.format(content=content), validation, bus
        )
