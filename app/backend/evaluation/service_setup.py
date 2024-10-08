import json
import logging
import os

import aiohttp
import openai
import requests
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureDeveloperCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from promptflow.core import (
    AzureOpenAIModelConfiguration,
    ModelConfiguration,
    OpenAIModelConfiguration,
)
from pyrit.chat_message_normalizer import ChatMessageNop, ChatMessageNormalizer
from pyrit.prompt_target import (
    AzureMLChatTarget,
    AzureOpenAITextChatTarget,
    OpenAIChatTarget,
    PromptChatTarget,
)

from evaluation.app_chat_target import AppChatTarget

logger = logging.getLogger("evaluation")


def _log_env_vars():
    """Log required environment variables for debugging."""
    vars = [
        "OPENAI_HOST",
        "AZURE_SEARCH_SERVICE",
        "AZURE_SEARCH_INDEX",
        "AZURE_SEARCH_KEY",
        "BACKEND_URI",
        "AZURE_OPENAI_KEY",
        "AZURE_OPENAI_SERVICE",
        "AZURE_OPENAI_EVAL_DEPLOYMENT",
        "AZURE_OPENAI_EVAL_ENDPOINT",
        "OPENAI_API_KEY",
        "OPENAI_ORGANIZATION",
        "AZURE_ML_ENDPOINT",
        "AZURE_ML_MANAGED_KEY",
        "TENANT_ID",
        "CLIENT_ID",
        "CLIENT_SECRET",
        "AZURE_PRINCIPAL_ID",
    ]
    logger.debug("Environment Variables:")
    for var in vars:
        logger.debug(f"{var}: {os.environ.get(var)}")


def get_models(target_url: str) -> list:
    """Send request to /getmodels to determine whether the chosen model names are valid."""
    r = requests.get(target_url)
    r.raise_for_status()

    try:
        response_list = r.json()
    except json.JSONDecodeError:
        raise ValueError(f"Response is not valid JSON: {r.text}")
    return response_list


async def get_models_async(target_url: str) -> list:
    """Send async request to /getmodels to determine whether the chosen model names are valid."""
    async with aiohttp.ClientSession() as session:
        async with session.get(target_url) as response:
            response.raise_for_status()

            try:
                response_json = await response.json()
                if not isinstance(response_json, list):
                    raise ValueError(f"Expected a list, but got {type(response_json).__name__}")
                return response_json
            except aiohttp.ContentTypeError:
                raise ValueError(f"Response is not valid JSON: {await response.text}")


def get_openai_config() -> ModelConfiguration:
    """Get OpenAI configuration."""
    _log_env_vars()
    if os.environ.get("OPENAI_HOST") == "azure":
        azure_endpoint = f"https://{os.environ['AZURE_OPENAI_SERVICE']}.openai.azure.com"
        azure_deployment = os.environ.get("AZURE_OPENAI_EVAL_DEPLOYMENT")
        api_version = "2023-07-01-preview"
        if os.environ.get("AZURE_OPENAI_KEY"):
            logger.info("Using Azure OpenAI Service with API Key from AZURE_OPENAI_KEY")
            openai_config = AzureOpenAIModelConfiguration(
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_version=api_version,
                api_key=os.environ["AZURE_OPENAI_KEY"],
            )
        else:
            logger.info("Using Azure OpenAI Service with Azure Developer CLI Credential")
            openai_config = AzureOpenAIModelConfiguration(
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_version=api_version,
            )
            # PromptFlow will call DefaultAzureCredential behind the scenes
        openai_config.model = os.environ["AZURE_OPENAI_CHATGPT_MODEL"]
    else:
        logger.info("Using OpenAI Service with API Key from OPENAI_API_KEY")
        openai_config = OpenAIModelConfiguration(
            model=os.environ["AZURE_OPENAI_CHATGPT_MODEL"],
            api_key=os.environ.get("OPENAI_API_KEY"),
            organization=os.environ["OPENAI_ORGANIZATION"],
        )
    return openai_config


def get_openai_config_dict() -> dict:
    """Return a dictionary with OpenAI configuration based on environment variables.

    This is only used by azure-ai-generative SDK right now, and should be deprecated once
    the generate functionality is available in promptflow SDK.
    """
    if os.environ.get("OPENAI_HOST") == "azure":
        if os.environ.get("AZURE_OPENAI_KEY"):
            logger.info("Using Azure OpenAI Service with API Key from AZURE_OPENAI_KEY")
            api_key = os.environ["AZURE_OPENAI_KEY"]
        else:
            logger.info("Using Azure OpenAI Service with Azure Developer CLI Credential")
            azure_credential = AzureDeveloperCliCredential()
            api_key = azure_credential.get_token("https://cognitiveservices.azure.com/.default").token
        openai_config = {
            "api_type": "azure",
            "api_base": f"https://{os.environ['AZURE_OPENAI_SERVICE']}.openai.azure.com",
            "api_key": api_key,
            "api_version": "2024-02-15-preview",
            "deployment": os.environ["AZURE_OPENAI_EVAL_DEPLOYMENT"],
            "model": os.environ["AZURE_OPENAI_CHATGPT_MODEL"],
        }
    else:
        logger.info("Using OpenAI Service with API Key from OPENAI_API_KEY")
        openai_config = {
            "api_type": "openai",
            "api_key": os.environ["OPENAI_API_KEY"],
            "organization": os.environ["OPENAI_ORGANIZATION"],
            "model": os.environ["AZURE_OPENAI_CHATGPT_MODEL"],
            "deployment": "none-needed-for-openaicom",
        }
    return openai_config


def get_search_client() -> SearchClient:
    """Get Azure AI Search client."""
    if api_key := os.environ.get("AZURE_SEARCH_KEY"):
        logger.info("Using Azure Search Service with API Key from AZURE_SEARCH_KEY")
        azure_credential = AzureKeyCredential(api_key)
    else:
        logger.info("Using Azure Search Service with Azure Developer CLI Credential")
        azure_credential = AzureDeveloperCliCredential()

    return SearchClient(
        endpoint=f"https://{os.environ['AZURE_SEARCH_SERVICE']}.search.windows.net",
        index_name=os.environ["AZURE_SEARCH_INDEX"],
        credential=azure_credential,
    )


def get_openai_client(oai_config: ModelConfiguration) -> openai.OpenAI:
    """Get OpenAI client based on configuration."""
    if isinstance(oai_config, AzureOpenAIModelConfiguration):
        azure_token_provider = None
        if not os.environ.get("AZURE_OPENAI_KEY"):
            azure_token_provider = get_bearer_token_provider(
                AzureDeveloperCliCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
        logger.info(azure_token_provider)
        return openai.AzureOpenAI(
            api_version=oai_config.api_version,
            azure_endpoint=oai_config.azure_endpoint,
            api_key=oai_config.api_key if os.environ.get("AZURE_OPENAI_KEY") else None,
            azure_ad_token_provider=azure_token_provider,
            azure_deployment=oai_config.azure_deployment,
        )
    elif isinstance(oai_config, OpenAIModelConfiguration):
        oai_config: OpenAIModelConfiguration = oai_config
        return openai.OpenAI(api_key=oai_config.api_key, organization=oai_config.organization)
    else:
        raise ValueError(f"Unsupported OpenAI configuration type: {type(oai_config)}")


def get_openai_target() -> PromptChatTarget:
    """Get specified OpenAI chat target."""
    if os.environ["OPENAI_HOST"] == "azure":
        logger.info("Using Azure OpenAI Chat Target")
        deployment = os.environ["AZURE_OPENAI_EVAL_DEPLOYMENT"]
        endpoint = os.environ["AZURE_OPENAI_EVAL_ENDPOINT"]
        if api_key := os.environ.get("AZURE_OPENAI_KEY"):
            return AzureOpenAITextChatTarget(
                deployment_name=deployment,
                endpoint=endpoint,
                api_key=api_key,
            )
        else:
            return AzureOpenAITextChatTarget(deployment_name=deployment, endpoint=endpoint, use_aad_auth=True)
    else:
        logger.info("Using OpenAI Chat Target")
        return OpenAIChatTarget(api_key=os.environ["OPENAI_API_KEY"])


def get_app_target(config: dict, target_url: str = None) -> PromptChatTarget:
    """Get specified application chat target."""
    target_parameters = config.get("target_parameters", {})
    endpoint = os.environ["BACKEND_URI"].rstrip("/") + "/ask" if target_url is None else target_url
    logger.info("Using Application Chat Target")
    return AppChatTarget(endpoint_uri=endpoint, target_parameters=target_parameters)


def get_azure_ml_chat_target(
    chat_message_normalizer: ChatMessageNormalizer = ChatMessageNop,
) -> AzureMLChatTarget:
    """Get specified Azure ML chat target."""
    endpoint = os.environ["AZURE_ML_ENDPOINT"]
    api_key = os.environ["AZURE_ML_MANAGED_KEY"]
    return AzureMLChatTarget(
        endpoint_uri=endpoint,
        api_key=api_key,
        chat_message_normalizer=chat_message_normalizer,
    )
