from abc import ABC
from typing import List

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam


class OpenAIClient(ABC):

    def __init__(self):
        self._client = None

    @property
    def client(self):
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    async def chat_completion(self, *args, **kwargs) -> ChatCompletion:
        return await self.client.chat.completions.create(*args, **kwargs)

    def format_message(self, message: List[ChatCompletionMessageParam]) -> List[ChatCompletionMessageParam]:
        return message


class LocalOpenAIClient(OpenAIClient):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.client = AsyncOpenAI(*args, **kwargs)


class AzureOpenAIClient(OpenAIClient):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.client = AsyncAzureOpenAI(*args, **kwargs)
