from dataclasses import dataclass, field, fields
from typing import Optional

from api_wrappers import LLMClient


@dataclass
class ProtectionConfig:
    model_name: str
    use: bool = False


@dataclass
class PromptProtectionConfig:
    injection_protection: ProtectionConfig = field(
        default_factory=lambda: ProtectionConfig(model_name="protectai/deberta-v3-base-prompt-injection")
    )

    def empty_check(self) -> bool:
        for f in fields(self):
            if getattr(self, f.name).use:
                return False
        return True

    def setProtectionBool(self, protection_name: str, value: bool):
        individual_config = getattr(self, protection_name)
        if isinstance(individual_config, ProtectionConfig):
            individual_config.use = value

    def getModelName(self, protection_name: str) -> str:
        return getattr(self, protection_name).model_name


class PromptProtection:
    def __init__(self, config: Optional[PromptProtectionConfig]):
        if config:
            self.config = config
        else:
            self.config = PromptProtectionConfig()

    async def check_for_injection(self, message: str, llm_client: LLMClient, model: str) -> bool:
        result = await llm_client.text_classification(text=message, model=model)
        for element in result:
            if element.label == "SAFE" and element.score < 0.8:
                return True
        return False

    async def check_for_all_exploits(self, message: str, llm_client: LLMClient) -> bool:
        if self.config.empty_check():
            return True

        if self.config.injection_protection.use:
            if await self.check_for_injection(
                message=message, llm_client=llm_client, model=self.config.injection_protection.model_name
            ):
                return False

        return True
