# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from pyrit.chat_message_normalizer import ChatMessageNop, ChatMessageNormalizer
from pyrit.common import default_values, net_utility
from pyrit.memory import MemoryInterface
from pyrit.models import (
    ChatMessage,
    PromptRequestResponse,
    construct_response_from_request,
)
from pyrit.prompt_target import PromptChatTarget

from evaluation.utils import load_config

load_dotenv()

EVALUATION_DIR = Path(__file__).parent

logger = logging.getLogger(__name__)


class AppChatTarget(PromptChatTarget):

    BACKEND_URI: str = os.environ.get("BACKEND_URI", "").rstrip("/") + "/ask"

    def __init__(
        self,
        *,
        endpoint_uri: str = None,
        chat_message_normalizer: ChatMessageNormalizer = ChatMessageNop(),
        memory: MemoryInterface = None,
    ) -> None:

        PromptChatTarget.__init__(self, memory=memory)

        self.endpoint_uri: str = default_values.get_required_value(
            env_var_name=self.BACKEND_URI, passed_value=endpoint_uri
        )
        self.chat_message_normalizer = chat_message_normalizer

    async def send_prompt_async(self, *, prompt_request: PromptRequestResponse) -> PromptRequestResponse:

        self._validate_request(prompt_request=prompt_request)
        request = prompt_request.request_pieces[0]

        messages = self._memory.get_chat_messages_with_conversation_id(conversation_id=request.conversation_id)

        messages.append(request.to_chat_message())

        logger.info(f"Sending the following prompt to the prompt target: {request}")

        resp_text = await self._complete_chat_async(
            messages=messages,
        )

        if not resp_text:
            raise ValueError("The chat returned an empty response.")

        logger.info(f'Received the following response from the prompt target "{resp_text}"')
        return construct_response_from_request(request=request, response_text_pieces=[resp_text])

    async def _complete_chat_async(
        self,
        messages: list[ChatMessage],
    ) -> str:

        headers = self._get_headers()
        payload = self._construct_http_body(messages)

        response = await net_utility.make_request_and_raise_if_error_async(
            endpoint_uri=self.endpoint_uri, method="POST", request_body=payload, headers=headers
        )

        return response.json()["message"]["content"]

    def _construct_http_body(
        self,
        messages: list[ChatMessage],
    ) -> dict:
        """Constructs the HTTP request body for the application online endpoint."""
        config: Path = EVALUATION_DIR / "config.json"
        app_config = load_config(config)
        squashed_messages = self.chat_message_normalizer.normalize(messages)
        messages_dict = [message.model_dump() for message in squashed_messages]
        target_parameters = app_config.get("target_parameters", {})
        data = {
            "messages": [{"role": msg.get("role"), "content": msg.get("content")} for msg in messages_dict],
            "context": target_parameters,
        }
        return data

    def _get_headers(self) -> dict:

        headers: dict = {
            "Content-Type": "application/json",
        }

        return headers

    def _validate_request(self, *, prompt_request: PromptRequestResponse) -> None:
        if len(prompt_request.request_pieces) != 1:
            raise ValueError("This target only supports a single prompt request piece.")

        if prompt_request.request_pieces[0].converted_value_data_type != "text":
            raise ValueError("This target only supports text prompt input.")
