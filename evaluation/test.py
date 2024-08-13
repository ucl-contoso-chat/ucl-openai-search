import os
from os import path
from pathlib import Path

from evaluation.evaluate import plot_diagrams
from evaluation.evaluate_metrics import metrics_by_name
from evaluation.utils import load_jsonl

results_dirs = os.listdir("evaluation/results/gpt_evaluation")
results_dirs.sort(reverse=True)
result_dir = path.join("evaluation/results/gpt_evaluation", results_dirs[0])

questions_with_ratings = load_jsonl(path.join(result_dir, "eval_results.jsonl"))

requested_metrics = [
    "gpt_groundedness",
    "gpt_relevance",
    "gpt_coherence",
    "gpt_similarity",
    "gpt_fluency",
    "answer_length",
    "latency",
    "f1_score",
]
metrics = [metrics_by_name[metric_name] for metric_name in requested_metrics if metric_name in metrics_by_name]

plot_diagrams(questions_with_ratings, metrics, 4.0, Path(result_dir))
