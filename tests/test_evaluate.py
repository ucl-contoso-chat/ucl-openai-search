from datetime import timedelta
from unittest import mock

import requests
from promptflow.core import AzureOpenAIModelConfiguration

from evaluation.evaluate import (
    dump_summary,
    evaluate_row,
    send_question_to_target,
)
from evaluation.evaluate_metrics.base_metric import BaseMetric
from evaluation.service_setup import get_models


def test_evaluate_row():
    row = {"question": "What is the capital of France?", "truth": "Paris"}

    response = {
        "message": {"content": "This is the answer"},
        "context": {"data_points": {"text": ["Context 1", "Context 2"]}},
    }

    requests.post = lambda url, headers, json: MockResponse(response, url=url)
    target_url = "http://mock-target-url.com"
    openai_config = AzureOpenAIModelConfiguration("azure")
    openai_config.model = "mock_model"
    result = evaluate_row(
        row=row,
        target_url=target_url,
        openai_config=openai_config,
        requested_metrics=[MockMetric],
        target_parameters={"overrides": {"set_model": ""}},
    )

    assert result["question"] == "What is the capital of France?"
    assert result["truth"] == "Paris"
    assert "answer" in result
    assert "context" in result
    assert "latency" in result
    assert result["mock_metric_score"] == 1.0


def test_send_question_to_target_valid():
    # Test case 1: Valid response
    response = {
        "message": {"content": "This is the answer"},
        "context": {"data_points": {"text": ["Context 1", "Context 2"]}},
    }
    requests.post = lambda url, headers, json: MockResponse(response, url=url)
    result = send_question_to_target("Question 1", "http://example.com")
    assert result["answer"] == "This is the answer"
    assert result["context"] == "Context 1\n\nContext 2"
    assert result["latency"] == 1


def test_send_question_to_target_missing_error_store():
    response = {}
    requests.post = lambda url, headers, json: MockResponse(response, url=url)
    result = send_question_to_target("Question", "http://example.com", raise_error=False)
    assert result["answer"] == (
        "Response does not adhere to the expected schema. \n"
        "Either adjust the app response or adjust send_question_to_target() to match the actual schema.\n"
        "Response: {}"
    )
    assert result["context"] == (
        "Response does not adhere to the expected schema. \n"
        "Either adjust the app response or adjust send_question_to_target() to match the actual schema.\n"
        "Response: {}"
    )


def test_send_question_to_target_missing_all():
    response = {}
    requests.post = lambda url, headers, json: MockResponse(response, url=url)
    try:
        send_question_to_target("Question", "Answer", "http://example.com", raise_error=True)
    except Exception as e:
        assert str(e) == (
            "Response does not adhere to the expected schema. \n"
            "Either adjust the app response or adjust send_question_to_target() to match the actual schema.\n"
            "Response: {}"
        )


def test_send_question_to_target_missing_content():
    response = {
        "message": {},
        "context": {"data_points": {"text": ["Context 1", "Context 2"]}},
    }
    requests.post = lambda url, headers, json: MockResponse(response, url=url)
    try:
        send_question_to_target("Question", "Answer", "http://example.com", raise_error=True)
    except Exception as e:
        assert str(e) == (
            "Response does not adhere to the expected schema. \n"
            "Either adjust the app response or adjust send_question_to_target() to match the actual schema.\n"
            "Response: {'message': {}, 'context': {'data_points': {'text': ['Context 1', 'Context 2']}}}"
        )


def test_send_question_to_target_missing_context():
    # Test case 5: Missing 'context' key in response
    response = {"message": {"content": "This is the answer"}}
    requests.post = lambda url, headers, json: MockResponse(response, url=url)
    try:
        send_question_to_target("Question", "Answer", "http:/pytest/example.com", raise_error=True)
    except Exception as e:
        assert str(e) == (
            "Response does not adhere to the expected schema. \n"
            "Either adjust the app response or adjust send_question_to_target() to match the actual schema.\n"
            "Response: {'message': {'content': 'This is the answer'}}"
        )


def test_send_question_to_target_request_failed():
    # Test case 6: Request failed, response status code is 500
    requests.post = lambda url, headers, json: MockResponse(None, status_code=500, url=url)
    try:
        send_question_to_target("Question", "Answer", "http://example.com", raise_error=True)
    except Exception as e:
        assert isinstance(e, requests.HTTPError)


def test_get_models_success():
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = ["model1", "model2"]
    mock_response.text = '["model1", "model2"]'

    with mock.patch("requests.get", return_value=mock_response):
        models = get_models("http://fake-url.com/getmodels")
        assert models == ["model1", "model2"]


# @mock.patch("evaluation.evaluate.load_jsonl", return_value=[{"question": "What is 2 + 2?", "truth": "4"}])
# @mock.patch("evaluation.evaluate.dump_summary", return_value=None)
# @mock.patch("evaluation.evaluate.plot_diagrams", return_value=None)
# @mock.patch("evaluation.evaluate.service_setup.get_openai_config", return_value=OpenAIModelConfiguration(model="model"))
# @mock.patch("evaluation.evaluate.send_question_to_target", return_value={"answer": "4", "context": "2 + 2 = 4", "latency": 1.0})
# @mock.patch("evaluation.service_setup.get_models", return_value=["model_name"])
# @pytest.mark.asyncio
# async def test_run_evaluation_from_config(
#     mock_load_jsonl, mock_dump_summary, mock_plot_diagrams, mock_get_openai_config, mock_send_question_to_target, mock_get_models
# ):
#     with tempfile.TemporaryDirectory() as tempdir:
#         testdata_path = Path(tempdir) / "test_data.jsonl"
#         results_dir = Path(tempdir) / "results"

#         metrics_by_name["mock_metric"] = type(
#             "MockMetric",
#             (),
#             {
#                 "METRIC_NAME": "mock_metric",
#                 "evaluator_fn": staticmethod(
#                     lambda openai_config: lambda question, answer, context, ground_truth: {
#                         "mock_metric_score": 3.0
#                     }
#                 ),
#                 "get_aggregate_stats": staticmethod(
#                     lambda df, passing_rate: {"pass_rate": 0.67, "mean_rating": 3.0}
#                 ),
#             },
#         )

#         target_url = "http://mock-target-url.com"
#         openai_config = AzureOpenAIModelConfiguration("azure")
#         openai_config.model = "mock_model"
#         config = {
#             "testdata_path": testdata_path,
#             "results_dir": results_dir,
#             "passing_rate": 3,
#             "requested_metrics": ["mock_metric"],
#             "models": ["model_name"],
#             "max_workers": 2,
#             "target_parameters": {"overrides": {"set_model": ""}},
#         }

#         evaluation_config = get_evaluation_config(enabled=True, num_questions=200, target_url=target_url)
#         red_teaming_config = get_red_teaming_config(
#             enabled=True,
#             scorer_dir=DEFAULT_SCORER_DIR,
#             prompt_target="application",
#             max_turns=3,
#             config=config,
#             target_url=target_url,
#         )

#         success = await run_evaluation_from_config(
#             working_dir=Path(tempdir),
#             config=config,
#             evaluation_config=evaluation_config,
#             red_teaming_config=red_teaming_config,
#         )

#         assert success


def test_dump_summary(tmp_path):
    rated_questions_for_models = {
        "model1": [
            {"question": "What is the capital of France?", "answer": "Paris", "truth": "Paris"},
            {"question": "What is 2 + 2?", "answer": "4", "truth": "4"},
        ]
    }
    requested_metrics = []
    passing_rate = 3
    results_dir = tmp_path

    summary = dump_summary(rated_questions_for_models, requested_metrics, passing_rate, results_dir)
    assert summary is not None
    assert results_dir.joinpath("summary.json").exists()


class MockResponse:
    def __init__(self, json_data, status_code=200, reason="Fail Test", url="http://mock-url.com"):
        self.json_data = json_data
        self.status_code = status_code
        self.reason = reason
        self.elapsed = timedelta(seconds=1)
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.reason)

    @property
    def ok(self):
        return self.status_code >= 200 and self.status_code < 400

    def json(self):
        return self.json_data


class MockMetric(BaseMetric):
    METRIC_NAME = "mock_metric"
    DISPLAY_NAME = "Mock Evaluation Metric Rating"
    SHORT_NAME = "Mock Metric"
    NOTE = "Mock Rating Score"

    @staticmethod
    def evaluator_fn(openai_config):
        return lambda question, answer, context, ground_truth: {"mock_metric_score": 1.0}

    @classmethod
    def get_aggregate_stats(cls, df, passing_threshold=3):
        return {"pass_count": 1, "pass_rate": 1.0, "mean_rating": 5.0}
