import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import dotenv
import typer
from rich.logging import RichHandler

from evaluation import service_setup
from evaluation.config import get_evaluation_config, get_red_teaming_config, load_config
from evaluation.evaluate import run_evaluation_from_config
from evaluation.generate import generate_test_qa_answer, generate_test_qa_data

EVALUATION_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = EVALUATION_DIR / "config.json"
DEFAULT_SCORER_DIR = EVALUATION_DIR / "scorer_definitions"
DEFAULT_SYNTHETIC_DATA_DIR = EVALUATION_DIR / "input" / "qa.jsonl"
DEFAULT_SYNTHETIC_DATA_ANSWERS_DIR = EVALUATION_DIR / "output" / "qa.jsonl"

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
available_models = asyncio.run(service_setup.get_models_async(get_model_url))


def int_or_none(raw: str) -> Optional[int]:
    return None if raw == "None" else int(raw)


def str_or_none(raw: str) -> Optional[str]:
    return None if raw == "None" else raw


@app.command()
def run(
    evaluation: bool = typer.Option(True, help="Enable or disable running the evaluation."),
    red_teaming: bool = typer.Option(True, help="Enable or disable running the red teaming evaluation."),
    target_url: Optional[str] = typer.Option(
        help="URL of the target service to evaluate (defaults to the value of the BACKEND_URI environment variable).",
        default=None,
        parser=str_or_none,
    ),
    config: Path = typer.Option(
        exists=True,
        dir_okay=False,
        file_okay=True,
        help=(
            "Path to the configuration JSON file."
            " Edit the JSON file to specify the list of models to be evaluated/compared."
            f" The available models are: {', '.join(available_models)}"
        ),
        default=DEFAULT_CONFIG_PATH,
    ),
    report_output: Optional[Path] = typer.Option(
        help="Path for the PDF report output file to be generated.",
        default=None,
        dir_okay=False,
        file_okay=True,
    ),
    evaluation_num_questions: Optional[int] = typer.Option(
        help="Number of questions to use for GPT evaluation (defaults to all if not specified).",
        default=None,
        parser=int_or_none,
    ),
    red_teaming_prompt_target: Optional[str] = typer.Option(
        default="application",
        help="Specify the target of the red teaming approach. Must be one of: 'application', 'azureopenai', 'azureml'.",
    ),
    red_teaming_scorer_dir: Path = typer.Option(
        exists=True,
        dir_okay=True,
        file_okay=False,
        help="Path to the directory where the scorer YAML files are stored.",
        default=DEFAULT_SCORER_DIR,
    ),
    red_teaming_max_turns: int = typer.Option(
        default=3, help="The maximum number of turns to apply the attack strategy for."
    ),
):
    config = load_config(config)

    evaluation_config = get_evaluation_config(
        enabled=evaluation,
        num_questions=evaluation_num_questions,
        target_url=target_url,
    )

    red_teaming_config = get_red_teaming_config(
        enabled=red_teaming,
        scorer_dir=red_teaming_scorer_dir,
        prompt_target=red_teaming_prompt_target,
        max_turns=red_teaming_max_turns,
        config=config,
        target_url=target_url,
    )

    report_path = asyncio.run(
        run_evaluation_from_config(
            working_dir=EVALUATION_DIR,
            config=config,
            evaluation_config=evaluation_config,
            red_teaming_config=red_teaming_config,
            report_output=report_output,
        )
    )
    if report_path:
        typer.echo(f"Evaluation completed successfully, results saved to {report_path.absolute().as_posix()}")
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
    num_questions: int = typer.Option(help="Number of questions to generate.", default=200),
    per_source: int = typer.Option(help="Number of questions to generate per source.", default=5),
):
    generate_test_qa_data(
        openai_config=service_setup.get_openai_config_dict(),
        search_client=service_setup.get_search_client(),
        num_questions_total=num_questions,
        num_questions_per_source=per_source,
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


def cli():
    app()
