from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union

BASE_DIR = Path(__file__).resolve().parent


@dataclass
class ModelConfig:
    model_name: str
    display_name: str
    template_path: Path
    type: str  # ["openai", "hf"]
    identifier: Optional[str] = None


MODEL_CONFIGS: Dict[str, Union[ModelConfig, dict[str, ModelConfig]]] = {
    # OpenAI Configs
    "GPT 3.5 Turbo": {
        "openai": ModelConfig(
            model_name="gpt-3.5-turbo", display_name="GPT 3.5 Turbo", template_path=BASE_DIR / "openai", type="openai"
        ),
        "azure": ModelConfig(
            model_name="gpt-35-turbo", display_name="GPT 3.5 Turbo", template_path=BASE_DIR / "openai", type="openai"
        ),
    },
    # Hugging Face
    "Mistral AI 7B": ModelConfig(
        model_name="mistralai/Mistral-7B-Instruct-v0.3",
        display_name="Mistral AI 7B",
        template_path=BASE_DIR / "hf_mistralai",
        type="hf",
        identifier="mistralai/Mistral-7B-Instruct-v0.3",
    ),
    "Phi 3 Mini 4K": ModelConfig(
        model_name="microsoft/Phi-3-mini-4k-instruct",
        display_name="Phi 3 Mini 4K",
        template_path=BASE_DIR / "hf_phi3_mini_4k",
        type="hf",
        identifier="microsoft/Phi-3-mini-4k-instruct",
    ),
}


def get_supported_models(model_name: str, deployment_name: Optional[str] = None) -> dict[str, ModelConfig]:
    """This function returns the supported models based on the used OpenAI model and the deployment type.
    The deployment type is either "azure" or "openai", meaning that the model is either deployed on Azure or using OpenAI
    API directly. This function then concatenates the all supported Hugging Face models and the available OpenAI model.
    Args:
        model_name (str): The name of the OpenAI model.
        deployment_name (Optional[str]): The deployment name where the OpenAI is deployed.
    Returns:
        List[str]: A list of supported models.
    """
    supported_models = {}
    for key, model in MODEL_CONFIGS.items():
        if not isinstance(model, dict) and model.type == "hf":
            supported_models[key] = model
            continue

        if isinstance(model, dict):
            deployment_type = "azure" if deployment_name else "openai"
            openai_model = check_if_openai_model(model, deployment_type, model_name)

            if openai_model:
                openai_model.identifier = deployment_name if deployment_name else model_name
                supported_models[key] = openai_model

    return supported_models


def check_if_openai_model(
    model: Dict[str, ModelConfig], deployment_type: str, model_name: str
) -> Optional[ModelConfig]:
    """This function checks the dictionary of OpenAI models and returns the model for a given deployment
    type if it matches the required model name.
    Args:
        model (Dict[str, ModelConfig]): The dictionary of OpenAI models, both for deployment types 'azure' and 'openai'.
        deployment_type (str): The deployment type of the model ['azure', 'openai'].
        model_name (str): The name of the model to check.
    Returns:
        Optional[ModelConfig]: The model if it matches the required model name, else None
    """
    received_model = model[deployment_type]
    if received_model.model_name == model_name:
        return received_model
    return None
