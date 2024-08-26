import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import dotenv
import typer
from rich.logging import RichHandler

from evaluation import service_setup
from evaluation.evaluate import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_SCORER_DIR,
    DEFAULT_SYNTHETIC_DATA_ANSWERS_DIR,
    DEFAULT_SYNTHETIC_DATA_DIR,
    EVALUATION_DIR,
    run_evaluation_from_config,
)
from evaluation.generate import generate_test_qa_answer, generate_test_qa_data
from evaluation.red_teaming import run_red_teaming
from evaluation.utils import load_config

app = typer.Typer(pretty_exceptions_enable=False)

logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("evaluation")

logger.setLevel(logging.INFO)

dotenv.load_dotenv(override=True)

get_model_url = os.environ.get("BACKEND_URI") + "/getmodels"
# available_models = asyncio.run(get_models(get_model_url))
available_models = ["GPT 3.5 turbo", "Phi 3 Mini 4K", "Mistral AI 7B"]


def int_or_none(raw: str) -> Optional[int]:
    return None if raw == "None" else int(raw)


def str_or_none(raw: str) -> Optional[str]:
    return None if raw == "None" else raw


@app.command()
def evaluate(
    config: Path = typer.Option(
        exists=True,
        dir_okay=False,
        file_okay=True,
        help=f"Path to the configuration JSON file. The name of the model to be evaluated should be specified in the JSON file. The available models that you can choose from are: {', '.join(available_models)}",
        default=DEFAULT_CONFIG_PATH,
    ),
    numquestions: Optional[int] = typer.Option(
        help="Number of questions to evaluate (defaults to all if not specified).",
        default=None,
        parser=int_or_none,
    ),
    targeturl: Optional[str] = typer.Option(
        help="URL of the target service to evaluate (defaults to the value of the BACKEND_URI environment variable).",
        default=None,
        parser=str_or_none,
    ),
    report_output: Optional[Path] = typer.Option(
        help="Path to the PDF report output file (defaults to not generating a report).",
        default=None,
        dir_okay=False,
        file_okay=True,
    ),
):
    result = asyncio.run(
        run_evaluation_from_config(EVALUATION_DIR, load_config(config), numquestions, targeturl, report_output)
    ).result()
    if result:
        typer.echo("Evaluation completed successfully")
    else:
        typer.echo("Evaluation failed")


@app.command()
def generate(
    output: Path = typer.Option(
        exists=False,
        dir_okay=False,
        file_okay=True,
        default=DEFAULT_SYNTHETIC_DATA_DIR,
        help="Path for the output file that will be generated.",
    ),
    numquestions: int = typer.Option(help="Number of questions to generate.", default=200),
    persource: int = typer.Option(help="Number of questions to generate per source.", default=5),
):
    generate_test_qa_data(
        openai_config=service_setup.get_openai_config_dict(),
        search_client=service_setup.get_search_client(),
        num_questions_total=numquestions,
        num_questions_per_source=persource,
        output_file=output,
    )


@app.command()
def generate_answers(
    input: Path = typer.Option(
        exists=True,
        dir_okay=False,
        file_okay=True,
        default=DEFAULT_SYNTHETIC_DATA_DIR,
        help="Path to the input file.",
    ),
    output: Path = typer.Option(
        exists=False,
        dir_okay=False,
        file_okay=True,
        default=DEFAULT_SYNTHETIC_DATA_ANSWERS_DIR,
        help="Path for the output file to be generated.",
    ),
):
    generate_test_qa_answer(
        openai_config=service_setup.get_openai_config(),
        question_path=input,
        output_file=output,
    )


@app.command()
def red_teaming(
    config: Path = typer.Option(
        exists=True,
        dir_okay=False,
        file_okay=True,
        help="Path to the configuration JSON file.",
        default=DEFAULT_CONFIG_PATH,
    ),
    scorer_dir: Path = typer.Option(
        exists=True,
        dir_okay=True,
        file_okay=False,
        help="Path to the directory where the scorer YAML files are stored.",
        default=DEFAULT_SCORER_DIR,
    ),
    prompt_target: Optional[str] = typer.Option(
        default="application",
        help="Specify the target for the prompt. Must be one of: 'application', 'azureopenai', 'azureml'. use 'application' will use the first model in the config models list.",
    ),
    targeturl: Optional[str] = typer.Option(
        help="URL of the target service to evaluate (defaults to the value of the BACKEND_URI environment variable).",
        default=None,
        parser=str_or_none,
    ),
    max_turns: int = typer.Option(default=3, help="The maximum number of turns to apply the attack strategy."),
):
    config = load_config(config)
    red_team = service_setup.get_openai_target()
    if prompt_target == "application":
        target = service_setup.get_app_target(config, targeturl)
    elif prompt_target == "azureopenai":
        target = service_setup.get_openai_target()
    elif prompt_target == "azureml":
        target = service_setup.get_azure_ml_chat_target()
    else:
        raise ValueError(
            f"Invalid prompt_target value: {prompt_target}. Must be one of 'application', 'azureopenai', 'azureml'"
        )
    asyncio.run(
        run_red_teaming(
            working_dir=EVALUATION_DIR,
            scorer_dir=scorer_dir,
            config=config,
            red_teaming_llm=red_team,
            prompt_target=target,
            compare=False,
            max_turns=max_turns,
        )
    )


@app.command()
def red_teaming_comparison(
    config: Path = typer.Option(
        exists=True,
        dir_okay=False,
        file_okay=True,
        help=f"Path to the configuration JSON file. The available models that you can choose to compare are: {', '.join(available_models)}",
        default=DEFAULT_CONFIG_PATH,
    ),
    scorer_dir: Path = typer.Option(
        exists=True,
        dir_okay=True,
        file_okay=False,
        help="Path to the directory where the scorer YAML files are stored.",
        default=DEFAULT_SCORER_DIR,
    ),
    targeturl: Optional[str] = typer.Option(
        help="URL of the target service to evaluate (defaults to the value of the BACKEND_URI environment variable).",
        default=None,
        parser=str_or_none,
    ),
    max_turns: int = typer.Option(default=3, help="The maximum number of turns to apply the attack strategy."),
):
    config = load_config(config)
    red_team = service_setup.get_openai_target()
    target = service_setup.get_app_target(config, targeturl)
    asyncio.run(
        run_red_teaming(
            working_dir=EVALUATION_DIR,
            scorer_dir=scorer_dir,
            config=config,
            red_teaming_llm=red_team,
            prompt_target=target,
            compare=True,
            max_turns=max_turns,
        )
    )


def cli():
    app()
