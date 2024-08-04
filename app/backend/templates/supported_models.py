from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

OPENAI_MODELS = {
    "gpt-35-turbo": BASE_DIR / "openai",
    "gpt-3.5-turbo": BASE_DIR / "openai",
}
HF_MODELS = {
    "mistralai/Mistral-7B-Instruct-v0.3": BASE_DIR / "hf_mistralai",
}

SUPPORTED_MODELS = {**OPENAI_MODELS, **HF_MODELS}
