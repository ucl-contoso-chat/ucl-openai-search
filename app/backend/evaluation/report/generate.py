import enum
import os
from collections import defaultdict
from os import path
from pathlib import Path
from typing import Optional

import preppy

from evaluation.evaluate_metrics import metrics_by_name
from evaluation.evaluate_metrics.builtin_metrics import BuiltinRatingMetric
from evaluation.red_teaming import DISPLAY_LABEL_MAP, EXPECTED_VALUE
from evaluation.report.jsondict import condJSONSafe


class RML2PDFEngine(enum.Enum):
    TRML2PDF = 1
    REPORTLAB = 2
    Z3C = 3


RML2PDF_ENGINE = RML2PDFEngine.Z3C
REPORT_TEMPLATE = Path("evaluation/report/template.prep")
EVAL_RESULTS_DIR = Path("evaluation/results/")
# FIXME: Output into a timestamped directory
DEFAULT_OUTPUT_PATH = Path("evaluation/report/evaluation_report.pdf")


def generate_evaluation_report(
    summary: dict,
    eval_results: dict,
    redteaming_result: Optional[dict],
    results_dir: Optional[str],
    output_path: Optional[str],
    include_conversation: Optional[bool] = False,
):
    if results_dir is None:
        results_dir_ls = os.listdir(EVAL_RESULTS_DIR)
        results_dir_ls.sort(reverse=True)
        results_dir_ls = [d for d in results_dir_ls if path.isdir(path.join(EVAL_RESULTS_DIR, d))]
        if len(results_dir_ls) == 0:
            raise ValueError("No evaluation results found.")
        results_dir = path.join(EVAL_RESULTS_DIR, results_dir_ls[0])

    output_path = DEFAULT_OUTPUT_PATH if output_path is None else output_path

    template = preppy.getModule(REPORT_TEMPLATE)

    model_summaries = []
    for model, result in summary.items():
        gpt_summary, stat_summary = {}, {}
        for key, value in result.items():
            if key in metrics_by_name:
                metric = metrics_by_name[key]
                value["title"] = metric.DISPLAY_NAME
                value = condJSONSafe(value)
                if issubclass(metric, BuiltinRatingMetric):
                    gpt_summary[key] = value
                else:
                    stat_summary[key] = value

        gpt_summary = condJSONSafe(gpt_summary)
        stat_summary = condJSONSafe(stat_summary)
        model_summaries.append(
            condJSONSafe({"model_name": model, "gpt_summary": gpt_summary, "stat_summary": stat_summary})
        )

    conversation_results = defaultdict(list)
    for model_name, questions in eval_results.items():
        for res in questions:
            metric_values = []
            model_name = res["model_name"]
            conversasion_data = {}
            for key, value in res.items():
                if key in metrics_by_name:
                    metric_value = {}
                    metric = metrics_by_name[key]
                    metric_value["title"] = metric.DISPLAY_NAME

                    if issubclass(metric, BuiltinRatingMetric):
                        metric_value["unit"] = " / 5.0"
                    elif key == "answer_length":
                        metric_value["unit"] = "words"
                    elif key == "latency":
                        metric_value["unit"] = "seconds"

                    if isinstance(value, float):
                        value = round(value, 2)

                    metric_value["value"] = value
                    metric_values.append(condJSONSafe(metric_value))
                else:
                    conversasion_data[key] = value
            conversasion_data["metrics"] = condJSONSafe(metric_values)
            conversation_results[model_name].append(condJSONSafe(conversasion_data))

    conversation_results = condJSONSafe(conversation_results)

    num_questions = len(list(conversation_results.values())[0])

    diagrams = condJSONSafe(
        {
            "eval_results_path": path.join(results_dir, "evaluation_results.png"),
            "gpt_boxplot_path": path.join(results_dir, "evaluation_gpt_boxplot.png"),
            "stat_boxplot_path": path.join(results_dir, "evaluation_stat_boxplot.png"),
            "eval_radar_path": path.join(results_dir, "evaluation_gpt_radar.png"),
        }
    )

    contexts = {}
    for model, questions in eval_results.items():
        for question in questions:
            if "context" in question:
                context = question["context"].split("\n\n")
                for line in context:
                    splitter = line.find(":")
                    label = line[:splitter].strip()
                    text = line[splitter + 1 :].strip()
                    if label not in contexts:
                        contexts[label] = text
    contexts = condJSONSafe(contexts)

    if redteaming_result:
        redteaming_summary = {}
        for model, res in redteaming_result.items():
            redteaming_summary[model] = []
            for score in res:
                redteaming_summary[model].append(
                    condJSONSafe(
                        {
                            "label": DISPLAY_LABEL_MAP[score.score_category],
                            "value": ("Pass" if EXPECTED_VALUE[score.score_category] == score.score_value else "Fail"),
                            "description": score.score_rationale,
                        }
                    )
                )

        redteaming_result = condJSONSafe(redteaming_summary)

        diagrams["redteaming_results_table_path"] = path.join(results_dir, "red_teaming_results.png")

    passing_data = dict(
        total_questions=num_questions,
        summary=model_summaries,
        conversation_logs=conversation_results,
        diagrams=diagrams,
        contexts=contexts,
        redteaming_results=redteaming_result,
        include_conversation=include_conversation,
    )

    rml = template.getOutput(passing_data, quoteFunc=preppy.stdQuote)
    rml = str(rml, encoding="utf-8")

    rml_path = path.join(path.dirname(output_path), "evaluation_report.rml")
    with open(rml_path, "w+") as f:
        f.write(rml)

    if not path.exists(path.dirname(output_path)):
        os.makedirs(path.dirname(output_path))

    try:
        if RML2PDF_ENGINE == RML2PDFEngine.TRML2PDF:
            import trml2pdf

            trml2pdf.parseString(rml, output_path)
        elif RML2PDF_ENGINE == RML2PDFEngine.REPORTLAB:
            from rlextra.rml2pdf import rml2pdf as reoprtlab_rml2pdf

            reoprtlab_rml2pdf.rml2pdf.rml2pdf.go(rml, output_path)
        elif RML2PDF_ENGINE == RML2PDFEngine.Z3C:
            import z3c.rml.rml2pdf

            z3c.rml.rml2pdf.go(rml_path, outputFileName=output_path)
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return
