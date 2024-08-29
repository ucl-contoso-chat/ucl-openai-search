import asyncio
import json
import logging
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp
import numpy as np
import pandas as pd
import requests
from promptflow.core import AzureOpenAIModelConfiguration
from rich.progress import track

from evaluation import service_setup
from evaluation.evaluate_metrics import metrics_by_name
from evaluation.evaluate_metrics.builtin_metrics import BuiltinRatingMetric
from evaluation.plotting import (
    plot_bar_charts,
    plot_box_chart,
    plot_box_charts_grid,
    plot_radar_chart,
)
from evaluation.red_teaming import run_red_teaming
from evaluation.report_generator import (
    generate_eval_report,
)
from evaluation.service_setup import get_models_async
from evaluation.utils import load_jsonl

EVALUATION_RESULTS_DIR = "gpt_evaluation"

EVALUATION_DIR = Path(__file__).parent
DEFAULT_CONFIG_PATH = EVALUATION_DIR / "config.json"
DEFAULT_SCORER_DIR = EVALUATION_DIR / "scorer_definitions"
DEFAULT_SYNTHETIC_DATA_DIR = EVALUATION_DIR / "input" / "qa.jsonl"
DEFAULT_SYNTHETIC_DATA_ANSWERS_DIR = EVALUATION_DIR / "output" / "qa.jsonl"

logger = logging.getLogger("evaluation")


def send_question_to_target(question: str, url: str, parameters: dict = None, raise_error=True) -> dict:
    """Send a question to the ask endpoint and return the response."""
    headers = {
        "Content-Type": "application/json",
    }
    body = {
        "messages": [{"content": question, "role": "user"}],
        "context": parameters or {},
    }

    try:
        r = requests.post(url, headers=headers, json=body)

        r.raise_for_status()
        latency = r.elapsed.total_seconds()

        try:
            response_dict = r.json()
        except aiohttp.ContentTypeError:
            raise ValueError(
                f"Response from target {url} is not valid JSON:\n{r.text}"
                "Make sure that your configuration points at a chat endpoint that returns a single JSON object.\n"
            )
        try:
            answer = response_dict["message"]["content"]
            data_points = response_dict["context"]["data_points"]["text"]
            context = "\n\n".join(data_points)
        except Exception:
            raise ValueError(
                "Response does not adhere to the expected schema. \n"
                "Either adjust the app response or adjust send_question_to_target() to match the actual schema.\n"
                f"Response: {response_dict}"
            )

        response_obj = {"answer": answer,
                        "context": context, "latency": latency}
        return response_obj
    except Exception as e:
        if raise_error:
            raise e
        return {
            "answer": str(e),
            "context": str(e),
            "latency": -1,
        }


def evaluate_row(
    row,
    target_url: str,
    openai_config: dict,
    requested_metrics: list,
    target_parameters: dict,
) -> dict:
    """Evaluate a single row of test data."""
    output = {}
    output["question"] = row["question"]
    output["truth"] = row["truth"]
    output["model_name"] = target_parameters["overrides"]["set_model"]
    target_response = send_question_to_target(
        question=row["question"],
        url=target_url,
        parameters=target_parameters,
    )
    output.update(target_response)
    for metric in requested_metrics:
        result = metric.evaluator_fn(openai_config=openai_config)(
            question=row["question"],
            answer=output["answer"],
            context=output["context"],
            ground_truth=row["truth"],
        )
        output.update(result)
    return output


async def run_evaluation(
    openai_config: AzureOpenAIModelConfiguration,
    testdata_path: Path,
    results_dir: Path,
    target_url: str,
    passing_rate: int,
    max_workers: int,
    target_parameters: dict,
    requested_metrics: list,
    compared_models: list,
    num_questions: int = None,
):
    """Run evaluation on the provided test data."""
    # try:
    logger.info("Running evaluation using data from %s", testdata_path)
    testdata = load_jsonl(testdata_path)
    if num_questions:
        logger.info("Limiting evaluation to %s questions", num_questions)
        testdata = testdata[:num_questions]

    logger.info("Starting evaluation...")

    questions_with_ratings_dict = {}
    requested_metrics_list = requested_metrics
    for model in compared_models:
        target_parameters["overrides"]["set_model"] = model
        for metric in requested_metrics_list:
            if metric not in metrics_by_name:
                logger.error(
                    f"Requested metric {metric} is not available. Available metrics: {metrics_by_name.keys()}")
                return False

        requested_metrics = [
            metrics_by_name[metric_name] for metric_name in requested_metrics_list if metric_name in metrics_by_name
        ]

        questions_per_model_with_ratings = []

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            coroutines = [
                loop.run_in_executor(
                    executor,
                    evaluate_row,
                    row,
                    target_url,
                    openai_config,
                    requested_metrics,
                    target_parameters,
                )
                for row in testdata
            ]
            for eval_cor in track(asyncio.as_completed(coroutines), description="Processing..."):
                row_result = await eval_cor
                questions_per_model_with_ratings.append(row_result)

        logger.info(
            "Evaluation calls have completed. Calculating overall metrics now...")
        results_dir.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(results_dir / "eval_results.jsonl", "a", encoding="utf-8") as results_file:
            for row in questions_per_model_with_ratings:
                await results_file.write(json.dumps(row, ensure_ascii=False) + "\n")

        questions_with_ratings_dict.update(
            {model: questions_per_model_with_ratings})

    summary = dump_summary(questions_with_ratings_dict,
                           requested_metrics, passing_rate, results_dir)
    plot_diagrams(questions_with_ratings_dict,
                  requested_metrics, passing_rate, results_dir)
    # except Exception as e:
    #     logger.error("Evaluation was terminated early due to an error ⬆")
    #     raise e
    return (summary, questions_with_ratings_dict)


async def run_evaluation_from_config(
    working_dir: Path,
    config: dict,
    num_questions: int = None,
    target_url: str = None,
    report_output: Path = None,
):
    """Run evaluation using the provided configuration file."""

    run_redteaming = config.get("run_red_teaming", False)
    redteaming_max_turns = config.get("red_teaming_max_turns", 1)

    timestamp = int(time.time())
    if run_redteaming:
        results_dir = working_dir / \
            config["results_dir"] / f"experiment-{timestamp}"
    else:
        results_dir = working_dir / \
            config["results_dir"] / EVALUATION_RESULTS_DIR / \
            f"experiment-{timestamp}"
    results_dir.mkdir(parents=True, exist_ok=True)

    openai_config = service_setup.get_openai_config()
    testdata_path = working_dir / config["testdata_path"]
    max_workers = config.get("max_workers", 4)
    passing_rate = config.get("passing_rate", 3)
    target_parameters = config.get("target_parameters", {})
    requested_metrics = config.get(
        "requested_metrics",
        [
            "gpt_groundedness",
            "gpt_relevance",
            "gpt_coherence",
            "answer_length",
            "latency",
        ],
    )
    get_model_url = (os.environ.get("BACKEND_URI")
                     if target_url is None else target_url) + "/getmodels"
    compared_models = config.get("models")
    all_models = await get_models_async(get_model_url)

    unsupported_models = set(compared_models) - set(all_models)
    if unsupported_models:
        logger.error(
            f"Requested models {', '.join(unsupported_models)} are not available."
            f" Available models: {', '.join(all_models)}"
        )
        return False

    target_url = (os.environ.get("BACKEND_URI")
                  if target_url is None else target_url) + "/ask"

    summary, question_results = await run_evaluation(
        openai_config=openai_config,
        testdata_path=testdata_path,
        results_dir=results_dir,
        target_url=target_url,
        passing_rate=passing_rate,
        max_workers=max_workers,
        target_parameters=target_parameters,
        requested_metrics=requested_metrics,
        compared_models=compared_models,
        num_questions=num_questions,
    )

    red_teaming_results = None
    # Run red teaming if enabled
    if run_redteaming:
        red_teaming_llm = service_setup.get_openai_target()
        red_teaming_target = service_setup.get_app_target(config, target_url)

        red_teaming_results = await run_red_teaming(
            working_dir=working_dir,
            scorer_dir=DEFAULT_SCORER_DIR,
            config=config,
            red_teaming_llm=red_teaming_llm,
            prompt_target=red_teaming_target,
            max_turns=redteaming_max_turns,
            results_dir=results_dir,
        )

    if summary is not None:

        results_config_path = results_dir / "config.json"
        logger.info("Saving original config file back to %s",
                    results_config_path)

        # Replace relative paths with absolute paths in the original config
        config["testdata_path"] = str(testdata_path)
        config["results_dir"] = str(results_dir)

        # Add extra params to original config
        config["target_url"] = target_url
        config["evaluation_gpt_model"] = openai_config.model
        config["models"] = compared_models

        with open(results_config_path, "w", encoding="utf-8") as output_config:
            output_config.write(json.dumps(config, indent=4))

        if report_output is None or report_output == "":
            report_output = results_dir / "evaluation_report.pdf"
        
        include_conversation = config.get("include_conversation", False)
        generate_eval_report(
            summary, question_results, redteaming_result=red_teaming_results, results_dir=results_dir, output_path=report_output, include_conversation=include_conversation
        )
        logger.info("PDF Report generated at %s",
                    os.path.abspath(report_output))

        return True, results_dir
    else:
        shutil.rmtree(results_dir)
        logger.error("Evaluation was terminated early due to an error ⬆")
        return False, "Evaluation was terminated early"


# async def run_evaluation_by_request(
#     working_dir: Path, config: dict, num_questions: Optional[int] = None, target_url: Optional[str] = None
# ):
#     """Run evaluation from a backend request"""

#     logger.setLevel(logging.WARNING)

#     timestamp = int(time.time())
#     results_dir = working_dir / \
#         config["results_dir"] / f"experiment-{timestamp}"
#     results_dir.mkdir(parents=True, exist_ok=True)

#     run_redteaming = config.get("run_red_teaming", False)
#     redteaming_max_turns = config.get("red_teaming_max_turns", 1)

#     openai_config = service_setup.get_openai_config()
#     testdata_path = working_dir / config["testdata_path"]
#     max_workers = config.get("max_workers", 4)
#     passing_rate = config.get("passing_rate", 3)
#     target_parameters = config.get("target_parameters", {})
#     requested_metrics = config.get(
#         "requested_metrics",
#         [
#             "gpt_groundedness",
#             "gpt_relevance",
#             "gpt_coherence",
#             "answer_length",
#             "latency",
#         ],
#     )

#     get_model_url = (os.environ.get("BACKEND_URI")
#                      if target_url is None else target_url) + "/getmodels"
#     compared_models = config.get("models")
#     all_models = await get_models_async(get_model_url)
#     for elem in compared_models:
#         if elem not in all_models:
#             logger.error(
#                 f"Requested model {elem} is not available. Available metrics: {', '.join(all_models)}")
#             return False

#     target_url = (os.environ.get("BACKEND_URI")
#                   if target_url is None else target_url) + "/ask"

#     summary, question_results = await run_evaluation(
#         openai_config=openai_config,
#         testdata_path=testdata_path,
#         results_dir=results_dir,
#         target_url=target_url,
#         passing_rate=passing_rate,
#         max_workers=max_workers,
#         target_parameters=target_parameters,
#         requested_metrics=requested_metrics,
#         compared_models=compared_models,
#         num_questions=num_questions,
#     )

#     red_teaming_results = None
#     # Run red teaming if enabled
#     if run_redteaming:
#         red_teaming_llm = service_setup.get_openai_target()
#         red_teaming_target = service_setup.get_app_target(config, target_url)

#         red_teaming_results = await run_red_teaming(
#             working_dir=working_dir,
#             scorer_dir=DEFAULT_SCORER_DIR,
#             config=config,
#             red_teaming_llm=red_teaming_llm,
#             prompt_target=red_teaming_target,
#             max_turns=redteaming_max_turns,
#             results_dir=results_dir,
#         )

#     if summary is not None:
#         results_config_path = results_dir / "config.json"
#         logger.info("Saving original config file back to %s",
#                     results_config_path)

#         # Replace relative paths with absolute paths in the original config
#         config["testdata_path"] = str(testdata_path)
#         config["results_dir"] = str(results_dir)

#         # Add extra params to original config
#         config["target_url"] = target_url
#         config["evaluation_gpt_model"] = openai_config.model
#         config["models"] = compared_models

#         with open(results_config_path, "w", encoding="utf-8") as output_config:
#             output_config.write(json.dumps(config, indent=4))

#         include_conversation = config.get("include_conversation", False)

#         report_output = results_dir / "evaluation_report.pdf"
#         generate_eval_report(
#             summary,
#             question_results,
#             redteaming_result=red_teaming_results,
#             results_dir=results_dir,
#             output_path=report_output,
#             include_conversation=include_conversation,
#         )
#         logger.info("PDF Report generated at %s",
#                     os.path.abspath(report_output))

#         return results_dir
#     else:
#         shutil.rmtree(results_dir)
#         logger.error("Evaluation was terminated early due to an error ⬆")
#         return "Evaluation was terminated early"


def dump_summary(rated_questions_for_models: dict, requested_metrics: list, passing_rate: float, results_dir: Path):
    """Save the summary to a file."""

    summaries = []
    for key in rated_questions_for_models:
        rated_questions = rated_questions_for_models[key]
        summary = {}
        summary["model_name"] = key
        rated_questions_df = pd.DataFrame(rated_questions)
        results_per_model = {}
        for metric in requested_metrics:
            metric_result = metric.get_aggregate_stats(
                rated_questions_df, passing_rate)
            results_per_model[metric.METRIC_NAME] = metric_result
        summary["model_result"] = results_per_model
        summaries.append(summary)

    with open(results_dir / "summary.json", "a", encoding="utf-8") as summary_file:
        summary_file.write(json.dumps(summaries, indent=4))
    logger.info("Evaluation results saved in %s", results_dir)

    return summaries


def plot_diagrams(questions_with_ratings_dict: dict, requested_metrics: list, passing_rate: int, results_dir: Path):
    """Summarize the evaluation results and plot them."""
    rating_stat_data, stat_metric_data = {}, {}
    for key in questions_with_ratings_dict:
        rating_stat_data[key] = {"pass_count": {},
                                 "pass_rate": {}, "mean_rating": {}}
        stat_metric_data[key] = {"latency": {},
                                 "f1_score": {}, "answer_length": {}}
    requested_gpt_metrics, requested_stat_metrics = {}, {}
    gpt_metric_data_points, stat_metric_data_points = {}, {}

    width = 0.4  # the width of the bars

    for model, metrics_list in questions_with_ratings_dict.items():
        data_per_model = []
        for metrics in metrics_list:
            data_per_model.append(metrics)
            df = pd.DataFrame(data_per_model)
            data_dict_gpt, data_dict_stat = {}, {}
            for metric in requested_metrics:
                metric_name = metric.METRIC_NAME
                short_name = metric.SHORT_NAME
                data = df[metric_name].dropna()

                metric_result = metric.get_aggregate_stats(df, passing_rate)
                if issubclass(metric, BuiltinRatingMetric):  # If it's a GPT Rating metric
                    requested_gpt_metrics[metric_name] = metric
                    if len(data) > 0:
                        data_dict_gpt[short_name] = data.tolist()
                    for stat, value in metric_result.items():
                        rating_stat_data[model][stat][short_name] = value
                else:
                    requested_stat_metrics[metric_name] = metric
                    if len(data) > 0:
                        data_dict_stat[short_name] = data.tolist()
                    stat_metric_data[model][short_name] = metric_result
            gpt_metric_data_points[model] = data_dict_gpt
            stat_metric_data_points[model] = data_dict_stat
    display_stats_name = {
        "pass_count": "Pass Count",
        "pass_rate": "Pass Rate",
        "mean_rating": "Average Rating",
    }

    stats_y_labels = {
        "pass_count": "Number of Questions",
        "pass_rate": "Percentage",
        "mean_rating": "Rating Score",
    }

    stats_y_lim = {
        "pass_count": len(questions_with_ratings_dict[next(iter(questions_with_ratings_dict))]),
        "pass_rate": 1.0,
        "mean_rating": 5.0,
    }
    # Draw the chart for the results
    data = {}
    for key in questions_with_ratings_dict:
        data_per_model = [data for _, data in rating_stat_data[key].items()]
        data[key] = data_per_model
        titles = [display_stats_name[mn]
                  for mn in rating_stat_data[key].keys()]
        y_labels = [stats_y_labels[mn] for mn in rating_stat_data[key].keys()]
        y_lims = [stats_y_lim[mn] for mn in rating_stat_data[key].keys()]

    layout = (
        int(np.ceil(len(rating_stat_data[next(iter(rating_stat_data))]) / 3)),
        (
            3
            if len(rating_stat_data[next(iter(rating_stat_data))]) > 3
            else len(rating_stat_data[next(iter(rating_stat_data))])
        ),
    )

    plot_bar_charts(
        layout,
        data,
        titles,
        y_labels,
        results_dir / "evaluation_results.png",
        y_lims,
        width,
    )

    gpt_metric_avg_ratings, data_for_single_box, data_for_multi_box = {}, {}, {}
    for key in questions_with_ratings_dict:
        gpt_metric_avg_ratings[key] = list(
            rating_stat_data[key]["mean_rating"].values())
        data_for_single_box[key] = list(gpt_metric_data_points[key].values())
        data_for_multi_box[key] = list(stat_metric_data_points[key].values())
        label_for_single_box = list(gpt_metric_data_points[key].keys())
        titles_for_multi_box = list(stat_metric_data_points[key].keys())
    layout = (
        int(np.ceil(len(stat_metric_data_points[next(
            iter(stat_metric_data_points))]) / 3)),
        (
            3
            if len(stat_metric_data_points[next(iter(stat_metric_data_points))]) > 3
            else len(stat_metric_data_points[next(iter(stat_metric_data_points))])
        ),
    )
    gpt_metric_short_names = [m.SHORT_NAME for _,
                              m in requested_gpt_metrics.items()]
    plot_radar_chart(
        gpt_metric_short_names,
        gpt_metric_avg_ratings,
        "GPT Rating Metrics Results",
        results_dir / "evaluation_gpt_radar.png",
        5,
    )
    plot_box_chart(
        data_for_single_box,
        "GPT Ratings",
        label_for_single_box,
        "Rating Score",
        results_dir / "evaluation_gpt_boxplot.png",
        y_lim=(0.0, 5.0),
    )

    y_labels = [metric.NOTE for _, metric in requested_stat_metrics.items()]

    plot_box_charts_grid(
        layout,
        data_for_multi_box,
        titles_for_multi_box,
        y_labels,
        results_dir / "evaluation_stat_boxplot.png",
    )
