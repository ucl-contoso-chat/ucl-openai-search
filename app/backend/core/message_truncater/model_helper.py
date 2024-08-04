from __future__ import annotations

import logging

import tiktoken
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionNamedToolChoiceParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolParam,
)
from transformers import AutoTokenizer  # type: ignore

from .function_format import format_function_definitions
from .images_helper import count_tokens_for_image

AOAI_2_OAI = {"gpt-35-turbo": "gpt-3.5-turbo", "gpt-35-turbo-16k": "gpt-3.5-turbo-16k", "gpt-4v": "gpt-4-turbo-vision"}

logger = logging.getLogger("openai_messages_token_helper")


def get_openai_encoding(model: str, default_to_cl100k=False) -> tiktoken.Encoding:
    """
    Get the encoding for a given GPT model name (OpenAI.com or Azure OpenAI supported).
    Args:
        model (str): The name of the model to get the encoding for.
        default_to_cl100k (bool): Whether to default to the CL100k encoding if the model is not found.
    Returns:
        tiktoken.Encoding: The encoding for the model.
    """
    if model == "" or model is None or (model not in AOAI_2_OAI and not default_to_cl100k):
        raise ValueError("Expected valid OpenAI GPT model name")
    model = AOAI_2_OAI.get(model, model)
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        if default_to_cl100k:
            logger.warning("Model %s not found, defaulting to CL100k encoding", model)
            return tiktoken.get_encoding("cl100k_base")
        else:
            raise


def count_tokens_for_message(
    model: str, model_type: str, message: ChatCompletionMessageParam, default_to_cl100k=False
) -> int:
    """
    Calculate the number of tokens required to encode a message.
    Some of the numbers are deliberately exaggerated to guarantee a successful API call.

    Args:
        model (str): The name of the model to use for encoding.
        model_type (str): The type of the model to use for encoding [openai, hf].
        message (Mapping): The message to encode, in a dictionary-like object.
        default_to_cl100k (bool): Whether to default to the CL100k encoding if the model is not found.
    Returns:
        int: The total number of tokens required to encode the message.

    >> model = 'gpt-3.5-turbo'
    >> model_type = 'openai'
    >> message = {'role': 'user', 'content': 'Hello, how are you?'}
    >> count_tokens_for_message(model, message)
    13
    """
    # Encoding is received via tiktoken if model is OpenAI, or from the AutoTokenizer
    # if model is set for HuggingFace Inference API.
    if model_type == "openai":
        encoding = get_openai_encoding(model, default_to_cl100k)
    elif model_type == "hf":
        try:
            encoding = AutoTokenizer.from_pretrained(model)
        except Exception as e:
            raise ValueError(f"Could not load Hugging Face model: {model}. Error: {e}")
    else:
        raise ValueError(f"Unsupported model type: {model_type}. Please add type: 'hf' or 'openai' in your template.")

    # Assumes we're using a recent model
    tokens_per_message = 3

    num_tokens = tokens_per_message
    for key, value in message.items():
        if isinstance(value, list):
            # For GPT-4-vision support, based on https://github.com/openai/openai-cookbook/pull/881/files
            for item in value:
                # Note: item[type] does not seem to be counted in the token count
                if item["type"] == "text":
                    num_tokens += len(encoding.encode(item["text"]))
                elif item["type"] == "image_url":
                    num_tokens += count_tokens_for_image(item["image_url"]["url"], item["image_url"]["detail"])
        elif isinstance(value, str):
            num_tokens += len(encoding.encode(value))
        else:
            raise ValueError(f"Could not encode unsupported message value type: {type(value)}")
        if key == "name":
            num_tokens += 1
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def count_tokens_for_system_and_tools(
    model: str,
    model_type: str,
    system_message: ChatCompletionSystemMessageParam | None = None,
    tools: list[ChatCompletionToolParam] | None = None,
    tool_choice: ChatCompletionNamedToolChoiceParam | None = None,
    default_to_cl100k: bool = False,
) -> int:
    """
    Calculate the number of tokens required to encode a system message and tools.
    Both must be calculated together because the count is lower if both are present.
    Based on https://github.com/forestwanglin/openai-java/blob/main/jtokkit/src/main/java/xyz/felh/openai/jtokkit/utils/TikTokenUtils.java

    Args:
        model (str): The name of the model to use for encoding.
        model_type (str): The type of the model to use for encoding [openai, hf].
        tools (list[dict[str, dict]]): The tools to encode.
        tool_choice (str | dict): The tool choice to encode.
        system_message (dict): The system message to encode.
        default_to_cl100k (bool): Whether to default to the CL100k encoding if the model is not found.
    Returns:
        int: The total number of tokens required to encode the system message and tools.
    """
    # Encoding is received via tiktoken if model is OpenAI, or from the AutoTokenizer
    # if model is set for HuggingFace Inference API.

    if model_type == "openai":
        encoding = get_openai_encoding(model, default_to_cl100k)
    elif model_type == "hf":
        try:
            encoding = AutoTokenizer.from_pretrained(model)
        except Exception as e:
            raise ValueError(f"Could not load Hugging Face model: {model}. Error: {e}")
    else:
        raise ValueError(f"Unsupported model type: {model_type}. Please add type: 'hf' or 'openai' in your template.")

    tokens = 0
    if system_message:
        tokens += count_tokens_for_message(model, model_type, system_message, default_to_cl100k)
    if tools:
        tokens += len(encoding.encode(format_function_definitions(tools)))
        tokens += 9  # Additional tokens for function definition of tools
    # If there's a system message and tools are present, subtract four tokens
    if tools and system_message:
        tokens -= 4
    # If tool_choice is 'none', add one token.
    # If it's an object, add 4 + the number of tokens in the function name.
    # If it's undefined or 'auto', don't add anything.
    if tool_choice == "none":
        tokens += 1
    elif isinstance(tool_choice, dict):
        tokens += 7
        tokens += len(encoding.encode(tool_choice["function"]["name"]))
    return tokens