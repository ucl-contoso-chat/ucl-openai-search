from typing import List

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam


class LocalOpenAIClient(AsyncOpenAI):

    def __init__(self, *args, **kwargs) -> None:
        AsyncOpenAI.__init__(self, *args, **kwargs)

    async def chat_completion(
        self,
        *args,
        **kwargs,
    ) -> ChatCompletion:
        return await self.chat.completions.create(*args, **kwargs)

    def format_message(self, message: List[ChatCompletionMessageParam]) -> List[ChatCompletionMessageParam]:
        return message
