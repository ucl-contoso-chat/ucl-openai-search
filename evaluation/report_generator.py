import enum
import json
import os
from os import path

import preppy

from evaluation.evaluate_metrics import metrics_by_name
from evaluation.evaluate_metrics.builtin_metrics import BuiltinRatingMetric
from evaluation.jsondict import condJSONSafe
from evaluation.utils import load_jsonl


class RML2PDFEngine(enum.Enum):
    TRML2PDF = 1
    REPORTLAB = 2
    Z3C = 3


RML2PDF_ENGINE = RML2PDFEngine.Z3C
REPORT_TEMPLATE = "evaluation/report_template/eval_report.prep"
EVAL_RESULTS_DIR = "evaluation/results/gpt_evaluation/"
DEFUALT_OUTPUT_PATH = "evaluation/report/eval_report.pdf"


def generate_eval_report(results_dir: str = "", output_path: str = ""):
    if results_dir == "":
        results_dir_ls = os.listdir(EVAL_RESULTS_DIR)
        results_dir_ls.sort(reverse=True)
        results_dir_ls = [d for d in results_dir_ls if path.isdir(path.join(EVAL_RESULTS_DIR, d))]
        if len(results_dir_ls) == 0:
            print("No evaluation results found.")
        results_dir = path.join(EVAL_RESULTS_DIR, results_dir_ls[0])

    output_path = output_path if output_path != "" else DEFUALT_OUTPUT_PATH

    template = preppy.getModule(REPORT_TEMPLATE)

    with open(path.join(results_dir, "summary.json")) as eval_json_file:
        summary = json.load(eval_json_file)

    model_summaries = []
    for model in summary:
        gpt_summary = {}
        stat_summary = {}
        for key, value in model["model_result"].items():
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
            condJSONSafe({"model_name": model["model_name"], "gpt_summary": gpt_summary, "stat_summary": stat_summary})
        )

    eval_results = load_jsonl(path.join(results_dir, "eval_results.jsonl"))
    conversation_results = {}

    for i in range(len(eval_results)):
        res = eval_results[i]
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
        if model_name not in conversation_results:
            conversation_results[model_name] = []
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
    for conversation in eval_results:
        if "context" in conversation:
            context = conversation["context"].split("\n\n")
            for line in context:
                splitter = line.find(":")
                label = line[:splitter].strip()
                text = line[splitter + 1 :].strip()
                if label not in contexts:
                    contexts[label] = text
    contexts = condJSONSafe(contexts)

    passin_data = dict(
        total_questions=num_questions,
        summary=model_summaries,
        conversation_logs=conversation_results,
        diagrams=diagrams,
        contexts=contexts,
    )

    rml = template.getOutput(passin_data, quoteFunc=preppy.stdQuote)
    rml = str(rml, encoding="utf-8")

    rml_path = path.join(path.dirname(output_path), "eval_report.rml")
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
