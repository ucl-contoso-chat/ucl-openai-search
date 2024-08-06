from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

OPENAI_MODELS = {
    "gpt-35-turbo": {
        "path": BASE_DIR / "openai",
        "type": "openai",
    },
    "GPT 3.5 Turbo": {
        "path": BASE_DIR / "openai",
        "type": "openai",
    },
}

OPENAI_VISION_MODELS = {}

HF_MODELS = {
    "mistralai/Mistral-7B-Instruct-v0.3": {
        "path": BASE_DIR / "hf_mistralai",
        "type": "hf",
    },
    "microsoft/Phi-3-mini-4k-instruct": {
        "path": BASE_DIR / "hf_phi3_mini_4k",
        "type": "hf",
    },
}
