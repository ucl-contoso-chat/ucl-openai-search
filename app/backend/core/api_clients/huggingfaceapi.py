from .baseapiclient import BaseAPIClient


class HuggingFaceAPIClient(BaseAPIClient):
    DEFAULT_TEMPERATURE = 1.4
    DEFAULT_MAX_LENGTH = 1024
    DEFAULT_RETURN_FULL_TEXT = False
    DEFAULT_TOP_K = 1
    DEFAULT_TOP_P = 0.8
    DEFAULT_REPETITION_PENALTY = 1
    DEFAULT_MAX_NEW_TOKENS = 150
    DEFAULT_USE_CACHE = False

    """
    The __init__ class is supposed to call the __init__ of the base class. By providing the enviromental variables names (for hugging face in this case),
    we are able to get the api key and url using the __init__ method of the base class.
    The ask method allows us to use any parameters we want (dependent on the LLM we are using).
    """

    def __init__(
        self,
    ):
        super().__init__("HUGGINGFACE_API_KEY", "HUGGINGFACE_API_URL")

    def ask_api(
        self,
        inputs: str,
        temperature: float = DEFAULT_TEMPERATURE,
        max_length: int = DEFAULT_MAX_LENGTH,
        return_full_text: bool = DEFAULT_RETURN_FULL_TEXT,
        top_k: int = DEFAULT_TOP_K,
        top_p: float = DEFAULT_TOP_P,
        repetition_penalty: float = DEFAULT_REPETITION_PENALTY,
        max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
        use_cache: bool = DEFAULT_USE_CACHE,
    ) -> dict:
        payload = {
            "inputs": inputs,
            "parameters": {
                "temperature": temperature,
                "max_length": max_length,
                "return_full_text": return_full_text,
                "top_k": top_k,
                "top_p": top_p,
                "repetition_penalty": repetition_penalty,
                "max_new_tokens": max_new_tokens,
            },
            "options": {"use_cache": use_cache},
        }
        return self.post_request(payload)
