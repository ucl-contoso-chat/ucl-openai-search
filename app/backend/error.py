import logging
from typing import Optional

from openai import APIError
from quart import jsonify

ERROR_MESSAGE = """The app encountered an error processing your request.
If you are an administrator of the app, view the full error in the logs. See aka.ms/appservice-logs for more information.
Error type: {error_type}
"""
ERROR_MESSAGE_FILTER = """Your message contains content that was flagged by the content filter."""

ERROR_MESSAGE_LENGTH = """Your message exceeded the context length limit for this model. Please shorten your message or change your settings to retrieve fewer search results."""


class PromptProtectionError(Exception):
    message: str
    code: Optional[str] = None

    def __init__(self, message: str, code: Optional[str]) -> None:
        super().__init__(message)
        self.code = code


def error_dict(error: Exception) -> dict:
    if (isinstance(error, APIError) or isinstance(error, PromptProtectionError)) and error.code == "content_filter":
        return {"error": ERROR_MESSAGE_FILTER}
    if isinstance(error, APIError) and error.code == "context_length_exceeded":
        return {"error": ERROR_MESSAGE_LENGTH}
    return {"error": ERROR_MESSAGE.format(error_type=type(error))}


def error_response(error: Exception, route: str, status_code: int = 500):
    logging.exception("Exception in %s: %s", route, error)
    if (isinstance(error, APIError) or isinstance(error, PromptProtectionError)) and error.code == "content_filter":
        status_code = 400
    return jsonify(error_dict(error)), status_code
