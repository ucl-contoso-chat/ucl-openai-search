import os
from abc import ABC, abstractmethod

import requests


class BaseAPIClient(ABC):
    """
    Base class for API clients that will be used to interact with different APIs (e.g. HuggingFace, AI Studio models)
    This class is expected to be inherited by other classes that will implement the ask_api method and provide the environmental variables to __init__:
    @param api_key_env_name: The name of the environmental variable that contains the API key
    @param api_url_env_name: The name of the environmental variable that contains the API URL
    """

    def __init__(self, api_key_env_name: str, api_url_env_name: str):
        self.api_key = os.getenv(api_key_env_name)
        self.api_url = os.getenv(api_url_env_name)
        self.headers = {"Authorization": "Bearer " + self.api_key}

    @abstractmethod
    def ask_api(self, *args, **kwargs) -> dict:
        """Abstract method that is going to be implemented by super classes providing API clients for HuggingFace and other APIs (e.g. AI Studio models)
        This method is supposed to make a request to the API and return the response as a dictionary"""
        pass

    def post_request(self, payload: dict) -> dict:
        response = requests.post(self.api_url, headers=self.headers, json=payload)
        return response.json()
