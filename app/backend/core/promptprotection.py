from dataclasses import dataclass
from typing import Dict


@dataclass
class ProtectionConfig:
    model_name: str
    enabled: bool = False

    async def check_for_violation(self, **kwargs) -> bool:
        raise NotImplementedError

    @staticmethod
    def run_if_enabled(func):
        async def wrapper(self, *args, **kwargs):
            if self.enabled:
                return await func(self, *args, **kwargs)
            return True

        return wrapper


@dataclass
class InjectionProtectionConfig(ProtectionConfig):
    model_name: str = "protectai/deberta-v3-base-prompt-injection"

    @ProtectionConfig.run_if_enabled
    async def check_for_violation(self, **kwargs) -> bool:

        required_args = frozenset(["llm_client", "message"])
        if not required_args.issubset(kwargs):
            raise ValueError(f"Missing required arguments: {required_args - kwargs.keys()}")
        llm_client, message = kwargs["llm_client"], kwargs["message"]
        result = await llm_client.text_classification(text=message, model=self.model_name)

        for element in result:
            if element.label == "INJECTION" and element.score > 0.8:
                return False
        return True


class PromptProtection:
    def __init__(self, prompt_protection_enabled=False):
        self.config: Dict = {
            "injection_protection": InjectionProtectionConfig(enabled=prompt_protection_enabled),
        }

    def set_protection_bool(self, protection_name: str, value: bool):
        if protection_name in self.config:
            self.config[protection_name].enabled = value
        else:
            raise ValueError(f"Protection {protection_name} not found.")

    async def check_for_all_exploits(self, **kwargs) -> bool:
        for protection in self.config.values():
            if not await protection.check_for_violation(**kwargs):
                return False
        return True
