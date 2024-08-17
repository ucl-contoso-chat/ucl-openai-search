import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

import requests
from promptflow.core import AzureOpenAIModelConfiguration, OpenAIModelConfiguration

from evaluation.evaluate import (
    evaluate_row,
    get_models,
    run_evaluation_from_config,
    send_question_to_target,
)
from evaluation.evaluate_metrics import metrics_by_name


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
        send_question_to_target("Question", "Answer", "http://example.com", raise_error=True)
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


def test_run_evaluation_from_config():
    with tempfile.TemporaryDirectory() as tempdir:
        testdata_path = Path(tempdir) / "test_data.jsonl"
        results_dir = Path(tempdir) / "results"

        with mock.patch("evaluation.evaluate.load_jsonl", return_value=[{"question": "What is 2 + 2?", "truth": "4"}]):
            with mock.patch("evaluation.evaluate.dump_summary", return_value=None):
                with mock.patch("evaluation.evaluate.plot_diagrams", return_value=None):
                    with mock.patch(
                        "evaluation.evaluate.service_setup.get_openai_config",
                        return_value=OpenAIModelConfiguration(model="model"),
                    ):
                        with mock.patch(
                            "evaluation.evaluate.send_question_to_target",
                            return_value={"answer": "4", "context": "2 + 2 = 4", "latency": 1.0},
                        ):
                            with mock.patch("evaluation.evaluate.get_models", return_value=["model_name"]):

                                metrics_by_name["mock_metric"] = type(
                                    "MockMetric",
                                    (),
                                    {
                                        "METRIC_NAME": "mock_metric",
                                        "evaluator_fn": staticmethod(
                                            lambda openai_config: lambda question, answer, context, ground_truth: {
                                                "mock_metric_score": 3.0
                                            }
                                        ),
                                        "get_aggregate_stats": staticmethod(
                                            lambda df, passing_rate: {"pass_rate": 0.67, "mean_rating": 3.0}
                                        ),
                                    },
                                )

                                target_url = "http://mock-target-url.com"
                                openai_config = AzureOpenAIModelConfiguration("azure")
                                openai_config.model = "mock_model"
                                config = {
                                    "testdata_path": testdata_path,
                                    "results_dir": results_dir,
                                    "passing_rate": 3,
                                    "requested_metrics": ["mock_metric"],
                                    "compared_models": ["model_name"],
                                    "max_workers": 2,
                                    "target_parameters": {"overrides": {"set_model": ""}},
                                }

                                success = run_evaluation_from_config(
                                    working_dir=Path(tempdir),
                                    config=config,
                                    target_url=target_url,
                                )

                                assert success


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


class MockMetric:
    METRIC_NAME = "mock_metric"

    @staticmethod
    def evaluator_fn(openai_config):
        return lambda question, answer, context, ground_truth: {"mock_metric_score": 1.0}
