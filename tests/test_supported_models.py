import pytest

from templates.supported_models import MODEL_CONFIGS, ModelConfig, get_supported_models


@pytest.fixture
def sample_azure_deployment():
    return {"type": "azure", "model_name": "gpt-35-turbo", "deployment_name": "azure"}


@pytest.fixture
def sample_openai_deployment():
    return {"type": "openai", "model_name": "gpt-3.5-turbo", "deployment_name": ""}


def test_model_config_structure():
    assert isinstance(MODEL_CONFIGS, dict)

    for model_name, config in MODEL_CONFIGS.items():
        if isinstance(config, dict):
            # Ensure both 'openai' and 'azure' keys exist in the dictionary
            assert "openai" in config, f"{model_name} config should have an 'openai' entry."
            assert "azure" in config, f"{model_name} config should have an 'azure' entry."
            assert isinstance(
                config["openai"], ModelConfig
            ), f"The 'openai' entry for {model_name} should be a ModelConfig."
            assert isinstance(
                config["azure"], ModelConfig
            ), f"The 'azure' entry for {model_name} should be a ModelConfig."

        elif isinstance(config, ModelConfig):
            assert config.type == "hf", f"{model_name} should be a Hugging Face model."


def test_get_supported_models_with_azure(sample_azure_deployment):
    supported_models = get_supported_models(sample_azure_deployment)

    assert "GPT 3.5 Turbo" in supported_models
    assert supported_models["GPT 3.5 Turbo"].identifier == "azure"
    assert supported_models["GPT 3.5 Turbo"].model_name == "gpt-35-turbo"
    assert supported_models["GPT 3.5 Turbo"].type == "openai"

    assert "Mistral AI 7B" in supported_models
    assert supported_models["Mistral AI 7B"].type == "hf"


def test_get_supported_models_with_openai_fallback(sample_openai_deployment):
    supported_models = get_supported_models(sample_openai_deployment)

    assert "GPT 3.5 Turbo" in supported_models
    assert supported_models["GPT 3.5 Turbo"].identifier == "gpt-3.5-turbo"
    assert supported_models["GPT 3.5 Turbo"].model_name == "gpt-3.5-turbo"
    assert supported_models["GPT 3.5 Turbo"].type == "openai"

    assert "Mistral AI 7B" in supported_models
    assert supported_models["Mistral AI 7B"].type == "hf"


def test_get_supported_models_hugging_face_only():
    openai_deployment = {"type": None, "model_name": None, "deployment_name": None}
    supported_models = get_supported_models(openai_deployment)

    assert "GPT 3.5 Turbo" not in supported_models
    assert "Mistral AI 7B" in supported_models
    assert supported_models["Mistral AI 7B"].type == "hf"
    assert "Llama 3 8B Instruct" in supported_models


def test_get_supported_models_invalid_openai_deployment():
    openai_deployment = {"type": "unknown_type", "model_name": "gpt-3.5-turbo", "deployment_name": None}
    supported_models = get_supported_models(openai_deployment)

    assert "GPT 3.5 Turbo" not in supported_models
    assert "Mistral AI 7B" in supported_models
    assert supported_models["Mistral AI 7B"].type == "hf"
