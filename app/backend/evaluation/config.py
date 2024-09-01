import json
from dataclasses import dataclass
from pathlib import Path

from pyrit.prompt_target import PromptChatTarget

from evaluation import service_setup


def load_config(config_path: Path) -> dict:
    """Load a JSON configuration file."""
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class EvaluationConfig:
    enabled: bool = True
    num_questions: int = 200
    target_url: str = None


@dataclass
class RedTeamingConfig:
    enabled: bool = True
    scorer_dir: Path = None
    red_teaming_llm: PromptChatTarget = None
    prompt_target: PromptChatTarget = None
    max_turns: int = 3


def get_evaluation_config(enabled: bool, num_questions: int, target_url: str) -> EvaluationConfig:
    """Get the evaluation configuration."""
    return EvaluationConfig(enabled=enabled, num_questions=num_questions, target_url=target_url)


def get_red_teaming_config(
    enabled: bool, scorer_dir: Path, prompt_target: PromptChatTarget, max_turns: int, config: dict, target_url: str
) -> RedTeamingConfig:
    """Get the red teaming configuration."""
    red_team = service_setup.get_openai_target()
    if prompt_target == "application":
        target = service_setup.get_app_target(config, target_url)
    elif prompt_target == "azureopenai":
        target = service_setup.get_openai_target()
    elif prompt_target == "azureml":
        target = service_setup.get_azure_ml_chat_target()
    else:
        raise ValueError(
            f"Invalid prompt_target value: {prompt_target}. Must be one of 'application', 'azureopenai', 'azureml'"
        )
    return RedTeamingConfig(
        enabled=enabled,
        scorer_dir=scorer_dir,
        red_teaming_llm=red_team,
        prompt_target=target,
        max_turns=max_turns,
    )
