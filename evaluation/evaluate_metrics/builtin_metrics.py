from promptflow.evals.evaluators import (
    CoherenceEvaluator,
    F1ScoreEvaluator,
    FluencyEvaluator,
    GroundednessEvaluator,
    RelevanceEvaluator,
    SimilarityEvaluator,
)

from .base_metric import DEFAULT_PASSING_THRESHOLD, BaseMetric


class BuiltinRatingMetric(BaseMetric):
    @classmethod
    def get_aggregate_stats(cls, df, passing_threshold=DEFAULT_PASSING_THRESHOLD):
        return cls.get_aggregate_stats_for_numeric_rating(df, cls.METRIC_NAME, passing_threshold)


class BuiltinRelevanceMetric(BuiltinRatingMetric):
    METRIC_NAME = "gpt_relevance"

    DISPLAY_TITLE = "GPT Relevance Rating"
    SHORT_NAME = "Relevance"
    Y_AXIS_LABEL = "Rating Score (1-5)"

    @classmethod
    def evaluator_fn(cls, openai_config, **kwargs):
        return RelevanceEvaluator(openai_config)


class BuiltinCoherenceMetric(BuiltinRatingMetric):
    METRIC_NAME = "gpt_coherence"

    DISPLAY_TITLE = "GPT Coherence Rating"
    SHORT_NAME = "Coherence"
    Y_AXIS_LABEL = "Rating Score (1-5)"

    @classmethod
    def evaluator_fn(cls, openai_config, **kwargs):
        return CoherenceEvaluator(openai_config)


class BuiltinGroundednessMetric(BuiltinRatingMetric):
    METRIC_NAME = "gpt_groundedness"

    DISPLAY_TITLE = "GPT Groundedness Rating"
    SHORT_NAME = "Groundedness"
    Y_AXIS_LABEL = "Rating Score (1-5)"

    @classmethod
    def evaluator_fn(cls, openai_config, **kwargs):
        return GroundednessEvaluator(openai_config)


class BuiltinSimilarityMetric(BuiltinRatingMetric):
    METRIC_NAME = "gpt_similarity"

    DISPLAY_TITLE = "GPT Similarity Rating"
    SHORT_NAME = "Similarity"
    Y_AXIS_LABEL = "Rating Score (1-5)"

    @classmethod
    def evaluator_fn(cls, openai_config, **kwargs):
        return SimilarityEvaluator(openai_config)


class BuiltinFluencyMetric(BuiltinRatingMetric):
    METRIC_NAME = "gpt_fluency"

    DISPLAY_TITLE = "GPT Fluency Rating"
    SHORT_NAME = "Fluency"
    Y_AXIS_LABEL = "Rating Score (1-5)"

    @classmethod
    def evaluator_fn(cls, openai_config, **kwargs):
        return FluencyEvaluator(openai_config)


class BuiltinF1ScoreMetric(BaseMetric):
    METRIC_NAME = "f1_score"

    DISPLAY_TITLE = "F1 Score"
    SHORT_NAME = "F1 Score"
    Y_AXIS_LABEL = "F1 Score"

    @classmethod
    def evaluator_fn(cls, **kwargs):
        return F1ScoreEvaluator()

    @classmethod
    def get_aggregate_stats(cls, df, passing_threshold=DEFAULT_PASSING_THRESHOLD):
        return {
            "mean": round(df[cls.METRIC_NAME].mean(), 2),
            "max": round(df[cls.METRIC_NAME].max(), 2),
            "min": round(df[cls.METRIC_NAME].min(), 2),
        }
