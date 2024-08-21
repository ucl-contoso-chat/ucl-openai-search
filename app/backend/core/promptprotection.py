from dataclasses import dataclass
from typing import Dict


@dataclass
class ProtectionMechanism:
    """Base class for a protection mechanism to detect a violation.

    Classes adding support for a specific protection mechanism should inherit from this class,
    implementing the `check_for_violation` method to detect issues in the input message.

    Attributes:
        model_name (str): The name of the model to use for the protection mechanism.
        enabled (bool): Whether the protection mechanism is enabled or not.
    """

    model_name: str
    enabled: bool = False

    async def check_for_violation(self, **kwargs) -> bool:
        """Check for a violation in the input message using a protection mechanism.

        Args:
            **kwargs: Arbitrary keyword arguments that are accepted by the specific protection mechanism.
                The implementation should ensure that all required arguments are provided.

        Returns:
            bool: False if the protection mechanism detects a violation (check failed), True otherwise (check succeeded).
        """
        raise NotImplementedError

    @staticmethod
    def run_if_enabled(func):
        """Decorator to run a method only if the `enabled` attribute is True for the protection mechanism."""

        async def wrapper(self, *args, **kwargs):
            if self.enabled:
                return await func(self, *args, **kwargs)
            return True

        return wrapper


@dataclass
class InjectionProtection(ProtectionMechanism):
    """Protection mechanism for detecting prompt injection attacks.

    Attributes:
        model_name (str): The name of the model to use for the protection mechanism.
        enabled (bool): Whether the protection mechanism is enabled or not.
    """

    model_name: str = "protectai/deberta-v3-base-prompt-injection"

    @ProtectionMechanism.run_if_enabled
    async def check_for_violation(self, **kwargs) -> bool:
        """Check for prompt injection attacks in the input message using a text classification LLM.

        Args:
            **kwargs: Arbitrary keyword arguments. For running `text_classification`,
                `llm_client` and `message` must be included.

        Returns:
            bool: False if the message contains a prompt injection (check failed), True otherwise (check succeeded).

        Raises:
            ValueError: If the required arguments (`llm_client` and `message`) are not provided.
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

    To add new protection mechanisms, create a new class inheriting from `ProtectonMechanism` and
    implement the respective `check_for_violation` method. Then, the new class should be added to
    the dict of registered protection mechanisms (i.e. `protections`) defined in the `__init__` method.

    Attributes:
        protections (Dict[str, ProtectionMechanism]): A dictionary containing all registered protection mechanisms.
    """

    def __init__(self, injection_protection_enabled=False):
        """Register and initialise the supported protection mechanisms.

        Initialise the `PromptProtection` class with the supported protection mechanisms, which are
        supposed to be subclasses of `ProtectionMechanism`. If new protection mechanisms are added,
        new arguments can be added to the constructor to allow enabling them dynamically (optional).

        Args:
            injection_protection_enabled (bool): Enable or disable the injection protection mechanism.
        """
        self.protections: Dict[str, ProtectionMechanism] = {
            "injection_protection": InjectionProtection(enabled=injection_protection_enabled),
        }

    def set_protection_bool(self, protection_name: str, value: bool):
        """Set the `enabled` attribute of the protection mechanism with the given name.

        Args:
            protection_name (str): The name of the protection mechanism to enable or disable.
            value (bool): Whether to enable or disable the protection mechanism.
        """
        if protection_name in self.protections:
            self.protections[protection_name].enabled = value
        else:
            raise ValueError(f"Protection {protection_name} not found.")

    async def check_all_exploits(self, **kwargs) -> bool:
        """Check for all exploits using the configured protection mechanisms.

        A registered protection mechanism will only run if it is enabled.

        Args:
            **kwargs: Arbitrary keyword arguments that are accepted by different protection mechanisms.

        Returns:
            bool: False if any of the protection mechanisms detects a violation (check failed),
                True otherwise (check succeeded).
        """
        for protection in self.protections.values():
            if not await protection.check_for_violation(**kwargs):
                return False
        return True
