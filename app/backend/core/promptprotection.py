from dataclasses import dataclass
from typing import Dict


@dataclass
class ProtectionMechanism:
    """Abstract method to check for a violation.
    This method should be implemented by subclasses to define a logic for specific protection mechanism,
    checking for a violation in the input message.

    Args:
        model_name (str): The name of the model to use for the protection mechanism.
        enabled (bool): Whether the protection mechanism is enabled or not.

    Returns:
        bool: False if the message does not violate the protection mechanism, True otherwise.
    """

    model_name: str
    enabled: bool = False

    async def check_for_violation(self, **kwargs) -> bool:
        raise NotImplementedError

    @staticmethod
    def run_if_enabled(func):
        """Decorator to run the function only if the 'enabled' attribute is True.

        Returns:
            Callable: the wrapped function only running if the protection mechanism is enabled.
        """

        async def wrapper(self, *args, **kwargs):
            if self.enabled:
                return await func(self, *args, **kwargs)
            return True

        return wrapper


@dataclass
class InjectionProtection(ProtectionMechanism):
    """Protection mechanism for detecting prompt injection attacks.
    All the protection mechanisms are supposed to be implemented as subclasses of ProtectionMechanism.

    Attributes:
        model_name (str): The name of the model to use for the protection mechanism.
        enabled (bool): Whether to use this protection mechanism or not.
    """

    model_name: str = "protectai/deberta-v3-base-prompt-injection"

    @ProtectionMechanism.run_if_enabled
    async def check_for_violation(self, **kwargs) -> bool:
        """Check for prompt injection attacks in the input message using the text specification LLM.

        Args:
            **kwargs: Arbitrary keyword arguments. For running text_classification, must include 'llm_client' and 'message'.

        Returns:
            bool: False if the message does contain a prompt injection, True otherwise.

        Raises:
            ValueError: If the required arguments ('llm_client' and 'message') are not provided.
        """

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
    """Class to manage various prompt protection mechanisms.
    To add new protection mechanisms, first the ProtectonMechanism class should be implemented.
    Then, the new class should be added to the config inside of the __init__ method.

    Attributes:
        config (Dict): A dictionary containing all the protection mechanisms.
    """

    def __init__(self, prompt_protection_enabled=False):
        """Initialise the PromptProtection class with the given protection mechanisms, which are supposed
        to be subclasses of ProtectionMechanism. Additionally, new arguments should be added to the constructor,
        to initialise the protection mechanisms on startup (optional).

        Args:
            prompt_protection_enabled (bool): Enable or disable the injection protection mechanism.
        """
        self.config: Dict = {
            "injection_protection": InjectionProtection(enabled=prompt_protection_enabled),
        }

    def set_protection_bool(self, protection_name: str, value: bool):
        """Set the 'enabled' attribute of the protection mechanism with the given name.

        Args:
            protection_name (str): The name of the protection mechanism to enable or disable.
            value (bool): Whether to enable or disable the protection mechanism.
        """
        if protection_name in self.config:
            self.config[protection_name].enabled = value
        else:
            raise ValueError(f"Protection {protection_name} not found.")

    async def check_all_exploits(self, **kwargs) -> bool:
        """Check for all exploits using the configured protection mechanisms.
        It will only run the protection mechanism stored in the config if it is enabled.

        Args:
            **kwargs: Arbitrary keyword arguments that are accepted by different protection mechanisms.

        Returns:
            bool: False if any of the protection mechanisms detect a violation, True otherwise.
        """
        for protection in self.config.values():
            if not await protection.check_for_violation(**kwargs):
                return False
        return True
