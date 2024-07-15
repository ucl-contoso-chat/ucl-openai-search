from openai import AsyncOpenAI


class LocalOpenAIClient(AsyncOpenAI):

    def __init__(self, *args, **kwargs) -> None:
        AsyncOpenAI.__init__(self, *args, **kwargs)

    async def chat_completion(
        self,
        *args,
        **kwargs,
    ):
        return await self.chat.completions.create(*args, **kwargs)

    def format_message(self, message: str):
        return message
