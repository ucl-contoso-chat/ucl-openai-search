import logging
from pathlib import Path
from typing import Optional

import dotenv
import typer
from rich.logging import RichHandler
import asyncio

from . import service_setup
from .evaluate import run_evaluate_from_config
from .generate import (
    generate_test_qa_answer,
    generate_test_qa_data,
)
from .red_teaming import run_red_teaming

app = typer.Typer(pretty_exceptions_enable=False)

logging.basicConfig(
    level=logging.WARNING, format="%(message)s", datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("scripts")

logger.setLevel(logging.INFO)

dotenv.load_dotenv(override=True)


def int_or_none(raw: str) -> Optional[int]:
    return None if raw == "None" else int(raw)


def str_or_none(raw: str) -> Optional[str]:
    return None if raw == "None" else raw


@app.command()
def evaluate(
    config: Path = typer.Option(
        exists=True, dir_okay=False, file_okay=True, help="Path to config.json", default="config.json"
    ),
    numquestions: Optional[int] = typer.Option(
        help="Number of questions to evaluate (defaults to all if not specified).", default=None, parser=int_or_none
    ),
    targeturl: Optional[str] = typer.Option(
        help="URL of the target service to evaluate against (defaults to the one in the config).",
        default=None,
        parser=str_or_none,
    ),
):
    run_evaluate_from_config(Path.cwd(), config, numquestions, targeturl)


@app.command()
def generate(
    output: Path = typer.Option(exists=False, dir_okay=False, file_okay=True),
    numquestions: int = typer.Option(help="Number of questions to generate", default=200),
    persource: int = typer.Option(help="Number of questions to generate per source", default=5),
):
    generate_test_qa_data(
        openai_config=service_setup.get_openai_config_dict(),
        search_client=service_setup.get_search_client(),
        num_questions_total=numquestions,
        num_questions_per_source=persource,
        output_file=Path.cwd() / output,
    )




# @app.command()
# def generate_answers(
#     input: Path = typer.Option(exists=True, dir_okay=False, file_okay=True),
#     output: Path = typer.Option(exists=False, dir_okay=False, file_okay=True),
# ):
#     generate_test_qa_answer(
#         openai_config=service_setup.get_openai_config(),
#         question_path=Path.cwd() / input,
#         output_file=Path.cwd() / output,
#     )

@app.command()
def red_teaming(
    scorer_path: Path =  typer.Option(exists=True, dir_okay=False, file_okay=True, default="scorer_definitions/key_logger_classifier.yaml"),
):
    asyncio.run(run_red_teaming(Path.cwd() / scorer_path))
    
def cli():
    app()
