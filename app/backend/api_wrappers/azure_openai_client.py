from typing import List

from openai import AsyncAzureOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam


class AzureOpenAIClient(AsyncAzureOpenAI):

    def __init__(self, *args, **kwargs) -> None:
        AsyncAzureOpenAI.__init__(self, *args, **kwargs)

    async def chat_completion(
        self,
        *args,
        **kwargs,
    ) -> ChatCompletion:
        return await self.chat.completions.create(*args, **kwargs)

    def format_message(self, message: List[ChatCompletionMessageParam]) -> List[ChatCompletionMessageParam]:
        return message
