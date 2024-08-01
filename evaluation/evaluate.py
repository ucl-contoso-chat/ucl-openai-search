import concurrent.futures
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from promptflow.core import AzureOpenAIModelConfiguration
from rich.progress import track

from evaluation import service_setup
from evaluation.evaluate_metrics import metrics_by_name
from evaluation.utils import load_jsonl

EVALUATION_RESULTS_DIR = "gpt_evaluation"

logger = logging.getLogger("evaluation")


def send_question_to_target(question: str, url: str, parameters: dict = {}, raise_error=True) -> dict:
    """Send a question to the ask endpoint and return the response."""
    headers = {
        "Content-Type": "application/json",
    }
    body = {
        "messages": [{"content": question, "role": "user"}],
        "context": parameters,
    }

    try:
        r = requests.post(url, headers=headers, json=body)
        r.encoding = "utf-8"
        latency = r.elapsed.total_seconds()

        r.raise_for_status()

        try:
            response_dict = r.json()
        except json.JSONDecodeError:
            raise ValueError(
                f"Response from target {url} is not valid JSON:\n\n{r.text} \n"
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

        response_obj = {"answer": answer, "context": context, "latency": latency}
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
    target_parameters: dict = {},
) -> dict:
    """Evaluate a single row of test data."""
    output = {}
    output["question"] = row["question"]
    output["truth"] = row["truth"]
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


def run_evaluation(
    openai_config: AzureOpenAIModelConfiguration,
    testdata_path: Path,
    results_dir: Path,
    target_url: str,
    passing_rate: int,
    max_workers: int,
    target_parameters: dict,
    requested_metrics: list,
    num_questions: int = None,
):
    """Run evaluation on the provided test data."""
    logger.info("Running evaluation using data from %s", testdata_path)
    testdata = load_jsonl(testdata_path)
    if num_questions:
        logger.info("Limiting evaluation to %s questions", num_questions)
        testdata = testdata[:num_questions]

    logger.info("Starting evaluation...")
    for metric in requested_metrics:
        if metric not in metrics_by_name:
            logger.error(f"Requested metric {metric} is not available. Available metrics: {metrics_by_name.keys()}")
            return False

    requested_metrics = [
        metrics_by_name[metric_name] for metric_name in requested_metrics if metric_name in metrics_by_name
    ]

    questions_with_ratings = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(evaluate_row, row, target_url, openai_config, requested_metrics, target_parameters): row
            for row in testdata
        }
        for future in track(concurrent.futures.as_completed(futures), description="Processing..."):
            row_result = future.result()
            questions_with_ratings.append(row_result)

    logger.info("Evaluation calls have completed. Calculating overall metrics now...")
    results_dir.mkdir(parents=True, exist_ok=True)

    with open(results_dir / "eval_results.jsonl", "w", encoding="utf-8") as results_file:
        for row in questions_with_ratings:
            results_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    summarize_results_and_plot(questions_with_ratings, requested_metrics, results_dir, passing_rate)
    return True


def run_evaluation_from_config(working_dir: Path, config: dict, num_questions: int = None, target_url: str = None):
    """Run evaluation using the provided configuration file."""
    timestamp = int(time.time())
    results_dir = working_dir / config["results_dir"] / EVALUATION_RESULTS_DIR / f"experiment-{timestamp}"
    results_dir.mkdir(parents=True, exist_ok=True)

    openai_config = service_setup.get_openai_config()
    testdata_path = working_dir / config["testdata_path"]

    evaluation_run_complete = run_evaluation(
        openai_config=openai_config,
        testdata_path=testdata_path,
        results_dir=results_dir,
        target_url=os.environ.get("BACKEND_URI") + "/ask" if target_url is None else target_url,
        target_parameters=config.get("target_parameters", {}),
        passing_rate=config.get("passing_rate", 3),
        max_workers=config.get("max_workers", 4),
        num_questions=num_questions,
        requested_metrics=config.get(
            "requested_metrics",
            [
                "gpt_groundedness",
                "gpt_relevance",
                "gpt_coherence",
                "answer_length",
                "latency",
            ],
        ),
    )

    if evaluation_run_complete:
        results_config_path = results_dir / "config.json"
        logger.info("Saving original config file back to %s", results_config_path)

        # Replace relative paths with absolute paths in the original config
        config["testdata_path"] = str(testdata_path)
        config["results_dir"] = str(results_dir)

        # Add extra params to original config
        config["target_url"] = target_url
        config["evaluation_gpt_model"] = openai_config.model

        with open(results_config_path, "w", encoding="utf-8") as output_config:
            output_config.write(json.dumps(config, indent=4))
    else:
        logger.error("Evaluation was terminated early due to an error ⬆")

def plot_bar_charts(layout: Tuple[int, int], data: List[Dict[str, any]], titles: List[str], y_labels: List[str], output_path: Path, width = 0.4):
    """Plot bar charts for the provided data."""
    assert layout[0] * layout[1] == len(data), "Number of data points must match the layout"
    
    fig, axs = plt.subplots(layout[0], layout[1], figsize=(layout[1] * 5, layout[0] * 4))
    fig.tight_layout(pad=3.0)
    
    for i, ax in enumerate(axs.flat):
        x_data = list(data[i].keys())
        y_data = list(data[i].values())
        name = titles[i]
        
        ax.bar(x_data, y_data, width=width, label=name)
        ax.set_title(name)
        ax.set_ylim(0, np.ceil(max(y_data) * 1.2))
        ax.set_ylabel(y_labels[i])
        
        for j, v in enumerate(y_data):
            ax.text(j, v*1.02, str(round(v, 2)), ha='center')
            
    plt.savefig(output_path)
    plt.close(fig)
    
def plot_box_charts(layout: Tuple[int, int], data: List[List[float]], titles: List[str], y_labels: List[str], output_path: Path):
    """Plot box charts for the provided data."""
    assert layout[0] * layout[1] == len(data), "Number of data points must match the layout"
    
    fig, axs = plt.subplots(layout[0], layout[1], figsize=(layout[1] * 5, layout[0] * 4))
    fig.tight_layout(pad=3.0)
    
    for i, ax in enumerate(axs.flat):
        ax.boxplot(data[i])
        ax.set_title(titles[i])
        ax.set_ylabel(y_labels[i])
        
    plt.savefig(output_path)
    plt.close(fig)

def plot_box_chart(data: List[float], title: str, x_labels: List[str], y_label: str, output_path: Path):
    """Plot a box chart for the provided data."""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.boxplot(data, patch_artist=True, tick_labels=x_labels)
    ax.set_title(title)
    ax.set_ylabel(y_label)
    plt.savefig(output_path)
    plt.close(fig)

def summarize_results_and_plot(
    questions_with_ratings: list, requested_metrics: list, results_dir: Path, passing_rate: int
):
    """Summarize the evaluation results and plot them."""
    df = pd.DataFrame(questions_with_ratings)
    summary = {}
    gpt_metric_list, numeric_metric_list = [], []
    rating_stat_data = {
        "pass_count": {},
        "pass_rate": {},
        "mean_rating": {},
    }
    num_stat_data = {
        "latency": {},
        "f1_score" : {},
        "answer_length": {}
    }
    aggregated_data_lists = {}
    
    width = 0.4  # the width of the bars
    
    gpt_metrics = [
        "gpt_groundedness",
        "gpt_relevance",
        "gpt_coherence",
        "gpt_similarity",
        "gpt_fluency"
    ]
    
    numeric_metrics = [
        "latency",
        "f1_score",
        "answer_length"
    ]
    
    display_metric_name = {
        "pass_count": "Pass Count",
        "pass_rate": "Pass Rate",
        "mean_rating": "Average Rating",
        "latency": "Latency (sec)",
        "f1_score": "F1 Score",
        "answer_length": "Answer Length (words)",
        "gpt_groundedness": "GPT Groundedness Rating",
        "gpt_relevance": "GPT Relevance Rating",
        "gpt_coherence": "GPT Coherence Rating",
        "gpt_similarity": "GPT Similarity Rating",
        "gpt_fluency": "GPT Fluency Rating"
    }
    
    short_metric_name = {
        "pass_count": "Pass Count",
        "pass_rate": "Pass Rate",
        "mean_rating": "Avg. Rating",
        "latency": "Latency",
        "f1_score": "F1 Score",
        "answer_length": "Length",
        "gpt_groundedness": "Groundedness",
        "gpt_relevance": "Relevance",
        "gpt_coherence": "Coherence",
        "gpt_similarity": "Similarity",
        "gpt_fluency": "Fluency"
    }
        
    metric_value_labels = {
        "pass_count": "Number of Questions",
        "pass_rate": "Percentage",
        "mean_rating": "Rating Score",
        "latency": "Seconds",
        "f1_score": "F1 Score",
        "answer_length": "Words",
        "gpt_groundedness": "Rating Score",
        "gpt_relevance": "Rating Score",
        "gpt_coherence": "Rating Score",
        "gpt_similarity": "Rating Score",
        "gpt_fluency": "Rating Score"
    }
    
    for metric in requested_metrics:
        metric_name = metric.METRIC_NAME
        data = df[metric_name].dropna()
        if len(data) > 0:
            aggregated_data_lists[metric_name] = data.tolist()
        
        metric_result = metric.get_aggregate_stats(df, passing_rate)
        summary[metric.METRIC_NAME] = metric_result
        if (metric.METRIC_NAME in gpt_metrics):
            gpt_metric_list.append(metric.METRIC_NAME)
            short_name = short_metric_name[metric_name]
            for stat, value in metric_result.items():
                rating_stat_data[stat][short_name] = value
        if metric.METRIC_NAME in numeric_metrics:
            numeric_metric_list.append(metric.METRIC_NAME)
            short_name = short_metric_name[metric_name]
            num_stat_data[short_name] = metric_result
    # Summary statistics
    with open(results_dir / "summary.json", "w", encoding="utf-8") as summary_file:
        summary_file.write(json.dumps(summary, indent=4))
    logger.info("Evaluation results saved in %s", results_dir)

    # Draw the chart for the results
    metrics = gpt_metric_list
    data = [data for _, data in rating_stat_data.items()]
    titles = [display_metric_name[mn] for mn in rating_stat_data.keys()]
    y_labels = [metric_value_labels[mn] for mn in rating_stat_data.keys()]

    plot_bar_charts((1, 3), data, titles, y_labels, results_dir / "evaluation_results.png", width)
    
    data = [aggregated_data_lists[m] for m in gpt_metric_list]
    labels = [short_metric_name[m] for m in gpt_metric_list]
    plot_box_chart(data, "GPT Ratings", labels, "Rating Score", results_dir / "evaluation_gpt_boxplot.png")

    data = [data for _, data in aggregated_data_lists.items()]
    titles = [display_metric_name[mn] for mn in aggregated_data_lists.keys()]
    y_labels = [metric_value_labels[mn] for mn in aggregated_data_lists.keys()]
    
    plot_box_charts((1, 3), data[4:], titles[4:], y_labels[4:], results_dir / "evaluation_stat_boxplot.png")
