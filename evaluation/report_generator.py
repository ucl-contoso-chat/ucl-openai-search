import enum
import json
import os
from os import path

import preppy

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
        if len(results_dir_ls) == 0:
            print("No evaluation results found.")
        results_dir = path.join(EVAL_RESULTS_DIR, results_dir_ls[0])

    output_path = output_path if output_path != "" else DEFUALT_OUTPUT_PATH

    template = preppy.getModule(REPORT_TEMPLATE)

    with open(path.join(results_dir, "summary.json")) as eval_json_file:
        summary = json.load(eval_json_file)
        summary = condJSONSafe(summary)

    eval_results = load_jsonl(path.join(results_dir, "eval_results.jsonl"))
    eval_results = condJSONSafe(eval_results)

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

    passin_data = dict(summary=summary, conversations=eval_results, diagrams=diagrams, contexts=contexts)

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
