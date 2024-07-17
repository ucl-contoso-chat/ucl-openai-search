import concurrent.futures
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jmespath
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from rich.progress import track

from . import service_setup
from .evaluate_metrics import metrics_by_name

logger = logging.getLogger("scripts")


def send_question_to_target(
    question: str,
    url: str,
    parameters: dict = {},
    raise_error=False,
    response_answer_jmespath="message.content",
    response_context_jmespath="context.data_points.text",
):
    headers = {"Content-Type": "application/json"}
    body = {
        "messages": [{"content": question, "role": "user"}],
        "context": parameters,
    }
    try:
        r = requests.post(url, headers=headers, json=body)
        r.encoding = "utf-8"

        latency = r.elapsed.total_seconds()

        try:
            response_dict = r.json()
        except json.JSONDecodeError:
            raise ValueError(
                f"Response from target {url} is not valid JSON:\n\n{r.text} \n"
                "Make sure that your configuration points at a chat endpoint that returns a single JSON object.\n"
            )

        try:
            answer = jmespath.search(response_answer_jmespath, response_dict)
            data_points = jmespath.search(response_context_jmespath, response_dict)
            context = "\n\n".join(data_points)
        except Exception:
            raise ValueError(
                "Response does not adhere to the expected schema. "
                f"The answer should be accessible via the JMESPath expression '{response_answer_jmespath}' "
                f"and the context should be accessible via the JMESPath expression '{response_context_jmespath}'. "
                "Either adjust the app response or adjust send_question_to_target() in evaluate.py "
                f"to match the actual schema.\nResponse: {response_dict}"
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


def send_question_to_ask(
    question: str,
    url: str,
    # token: str,
    parameters: dict = {},
    raise_error=False,
    response_answer_jmespath="message.content",
    response_context_jmespath="context.data_points.text",
):
    headers = {
        "Content-Type": "application/json",
        # "Authorization": f"Bearer {token}"
    }
    body = {
        "messages": [{"content": question, "role": "user"}],
        "context": parameters,
    }
    try:
        r = requests.post(url, headers=headers, json=body)
        r.encoding = "utf-8"
        latency = r.elapsed.total_seconds()

        try:
            response_dict = r.json()
        except json.JSONDecodeError:
            raise ValueError(
                f"Response from target {url} is not valid JSON:\n\n{r.text} \n"
                "Make sure that your configuration points at a chat endpoint that returns a single JSON object.\n"
            )
        try:
            expression = "message.content"
            answer = jmespath.search(expression, response_dict)
            data_points = jmespath.search("context.data_points.text", response_dict)
            context = "\n\n".join(data_points)
        except Exception:
            raise ValueError(
                "Response does not adhere to the expected schema. 111111111111111111111111111111"
                f"The answer should be accessible via the JMESPath expression '{response_answer_jmespath}' "
                f"and the context should be accessible via the JMESPath expression '{response_context_jmespath}'. "
                "Either adjust the app response or adjust send_question_to_ask() to match the actual schema.\nResponse: {response_dict}"
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


def truncate_for_log(s: str, max_length=50):
    return s if len(s) < max_length else s[:max_length] + "..."


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f.readlines()]


def run_evaluation(
    openai_config: dict,
    testdata_path: Path,
    results_dir: Path,
    target_url: str,
    passing_rate: int,
    max_workers: int,
    target_parameters={},
    requested_metrics=[],
    num_questions=None,
    target_response_answer_jmespath=None,
    target_response_context_jmespath=None,
):
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

    def evaluate_row(row):
        output = {}
        output["question"] = row["question"]
        output["truth"] = row["truth"]
        target_response = send_question_to_ask(
            question=row["question"],
            url=target_url,
            # token=token,
            parameters=target_parameters,
            response_answer_jmespath=target_response_answer_jmespath,
            response_context_jmespath=target_response_context_jmespath,
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

    questions_with_ratings = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(evaluate_row, row): row for row in testdata}
        for future in track(concurrent.futures.as_completed(futures), description="Processing..."):
            row_result = future.result()
            questions_with_ratings.append(row_result)

    logger.info("Evaluation calls have completed. Calculating overall metrics now...")
    # Make the results directory if it doesn't exist
    results_dir.mkdir(parents=True, exist_ok=True)
    # Save the results
    with open(results_dir / "eval_results.jsonl", "w", encoding="utf-8") as results_file:
        for row in questions_with_ratings:
            results_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Calculate aggregate metrics
    df = pd.DataFrame(questions_with_ratings)
    summary = {}
    metric_list = []
    pass_rate = []
    mean_rate = []
    metric_name = []
    max_list = []
    min_list = []
    mean_list = []
    for metric in requested_metrics:
        metric_result = metric.get_aggregate_stats(df, passing_rate)
        summary[metric.METRIC_NAME] = metric_result
        if (
            metric.METRIC_NAME == "gpt_groundedness"
            or metric.METRIC_NAME == "gpt_relevance"
            or metric.METRIC_NAME == "gpt_coherence"
            or metric.METRIC_NAME == "gpt_similarity"
            or metric.METRIC_NAME == "gpt_fluency"
        ):
            metric_list.append(metric.METRIC_NAME)
            pass_rate.append(metric_result.get("pass_rate"))
            mean_rate.append(metric_result.get("mean_rating"))
        if metric.METRIC_NAME == "latency" or metric.METRIC_NAME == "f1_score" or metric.METRIC_NAME == "answer_length":
            metric_name.append(metric.METRIC_NAME)
            max = metric_result.get("max")
            min = metric_result.get("min")
            mean = metric_result.get("mean")
            max_list.append(max)
            min_list.append(min)
            mean_list.append(mean)

    # Draw the chart for the results

    fig, ax1 = plt.subplots()
    # bar_labels = ['red', 'blue', '_red', 'orange']
    # bar_colors = ['tab:red', 'tab:blue', 'tab:red', 'tab:orange']

    ax1.bar(metric_list, pass_rate)

    ax1.set_ylabel("passing rate")
    ax1.set_title("Passing rate of evaluation metrics")
    plt.savefig("passing_rate.png")
    plt.close(fig)

    fig, ax2 = plt.subplots()
    # bar_labels = ['red', 'blue', '_red', 'orange']
    # bar_colors = ['tab:red', 'tab:blue', 'tab:red', 'tab:orange']

    ax2.bar(metric_list, mean_rate)

    ax2.set_ylabel("mean score")
    ax2.set_title("Mean score of evaluation metrics")
    plt.savefig("mean_score.png")
    plt.close(fig)

    penguin_means = {
        "Max": tuple(max_list),
        "Min": tuple(min_list),
        "Mean": tuple(mean_list),
    }

    x = np.arange(len(metric_name))  # the label locations
    width = 0.25  # the width of the bars
    multiplier = 0

    fig, ax3 = plt.subplots(layout="constrained")

    for attribute, measurement in penguin_means.items():
        offset = width * multiplier
        rects = ax3.bar(x + offset, measurement, width, label=attribute)
        ax3.bar_label(rects, padding=3)
        multiplier += 1

    # Add some text for labels, title and custom x-axis tick labels, etc.
    ax3.set_title("Evaluation results")
    ax3.set_xticks(x + width, tuple(metric_name))
    ax3.legend(loc="upper left", ncols=3)
    ax3.set_ylim(0, 250)

    plt.savefig("eval.png")
    plt.close(fig)

    # summary statistics
    with open(results_dir / "summary.json", "w", encoding="utf-8") as summary_file:
        summary_file.write(json.dumps(summary, indent=4))

    with open(results_dir / "evaluate_parameters.json", "w", encoding="utf-8") as parameters_file:
        parameters = {
            "evaluation_gpt_model": openai_config.model,
            "evaluation_timestamp": int(time.time()),
            "testdata_path": str(testdata_path),
            "target_url": target_url,
            "target_parameters": target_parameters,
            "num_questions": num_questions,
        }
        parameters_file.write(json.dumps(parameters, indent=4))
    logger.info("Evaluation results saved in %s", results_dir)
    return True


def process_config(obj: dict):
    """Replace special markers in a config dict with their values:
    * <TIMESTAMP> with current timestamp
    * <READFILE> with contents of file
    """
    if isinstance(obj, dict):
        for key in obj:
            if isinstance(obj[key], dict):
                process_config(obj[key])
            elif isinstance(obj[key], str) and "<TIMESTAMP>" in obj[key]:
                logger.info("Replaced %s in config with timestamp", key)
                obj[key] = obj[key].replace("<TIMESTAMP>", str(int(time.time())))
            elif isinstance(obj[key], str) and "<READFILE>" in obj[key]:
                with open(obj[key].replace("<READFILE>", ""), encoding="utf-8") as f:
                    logger.info("Replaced %s in config with contents of %s", key, f.name)
                    obj[key] = f.read()


def run_evaluate_from_config(working_dir, config_path, num_questions, target_url):
    config_path = working_dir / Path(config_path)
    logger.info("Running evaluation from config %s", config_path)
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
        process_config(config)

    results_dir = working_dir / Path(config["results_dir"])
    passing_rate = config["passing_rate"]

    evaluation_run_complete = run_evaluation(
        openai_config=service_setup.get_openai_config(),
        testdata_path=working_dir / config["testdata_path"],
        results_dir=results_dir,
        target_url=config["target_url"],
        target_parameters=config.get("target_parameters", {}),
        passing_rate=passing_rate,
        max_workers=4,
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
        target_response_answer_jmespath=config.get("target_response_answer_jmespath"),
        target_response_context_jmespath=config.get("target_response_context_jmespath"),
    )

    if evaluation_run_complete:
        results_config_path = results_dir / "config.json"
        logger.info("Saving original config file back to to %s", results_config_path)
        with open(config_path, encoding="utf-8") as input_config:
            with open(results_config_path, "w", encoding="utf-8") as output_config:
                output_config.write(input_config.read())
    else:
        logger.error("Evaluation was terminated early due to an error ⬆")
