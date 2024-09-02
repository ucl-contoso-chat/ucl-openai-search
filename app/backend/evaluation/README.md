# RAG Chat Evaluation and Red Teaming

This directory contains scripts and tools based on
[Azure-Samples/ai-rag-chat-evaluator](https://github.com/Azure-Samples/ai-rag-chat-evaluator)
and [Azure/PyRIT](https://github.com/Azure/PyRIT) to perform evaluation and red teaming on the chat app.
By default, the OpenAI GPT model is used as the evaluator to perform the evaluation.
As an alternative, you can either use an Azure-hosted OpenAI instance or openai.com.

## Prerequisites

All of the following instructions assume that you're running commands from inside the `app/backend` directory of the repository.
Before using the evaluation scripts, you'll need to:

- Have a live deployment of the chat application on Azure
- Be on an Azure-authenticated shell session.
  You can run the following commands to ensure you're logged in before proceeding:

  ```shell
  az login
  azd auth login
  ```

- Create a `.env` file with environment variables required by the evaluation scripts.
  You can follow the instructions in the [following](#create-env-file) section to achieve that.

### Create .env file

If you already have an existing deployment and an active `azd` environment, you can create the required .env file
by running the appropriate script depending on your platform:

```shell
# Shell
./scripts/create_eval_dotenv.sh

# Powershell
# If you encounter a permission error, you might need to change the execution policy to allow script execution.
# You can do this by running:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\create_eval_dotenv.ps1
```

### Change LLM used for evaluation

The provided solution offers multiple configuration combinations.
One of the most important ones is tweaking the LLM used for evaluation, with a few options currently exposed:

- OpenAI GPT on Azure (default)
- Other models deployed on Azure ML
- Instances provided by openai.com

In order to change the default behaviour, you will have to set the corresponding environment variables before running
the `create_eval_dotenv` script.

If you want to use other ML models deployed on Azure, you need to set the following environment variables:

```shell
# Shell
export AZURE_ML_ENDPOINT="<deployment-endpoint>"
export AZURE_ML_MANAGED_KEY="<access-key>"

# Powershell
$env:AZURE_ML_ENDPOINT = "<deployment-endpoint>"
$env:AZURE_ML_MANAGED_KEY = "<access-key>"
```

On the other hand, to use instances deployed on openai.com, you need to set the following environment variables:

```shell
# Shell
export OPENAI_ORGANIZATION="<openai-organization-name>"
export OPENAI_API_KEY="<access-key>"

# Powershell
$env:OPENAI_ORGANIZATION = "<openai-organization-name>"
$env:OPENAI_API_KEY = "<access-key>"
```

## Generate synthetic data for evaluation

In order to run the evaluator, you must first create a set of of questions with corresponding "ground truth" answers
which represent the ideal response to each question.
This is possible using the `generate` script which generates synthetic data based on documents stored in the deployed
Azure AI Search instance.
You can run it like this, specifying the path of the generated output file, the desired number of total question-answer
pairs, as well as the number of pairs per source (i.e. document):

```shell
python -m evaluation generate \
  --output=evaluation/input/qa.jsonl \
  --num-questions=200 \
  --per-source=5
```

Running the above will generate 200 question-answer pairs and store them in `evaluation/input/qa.jsonl`.

### Generate answers for Azure AI Studio evaluation

After generating the questions, you can run the command below to instruct the LLM to generate the answers in a format
that can be used as raw data to conduct evaluation through the Azure AI Studio:

```shell
python -m evaluation generate-answers \
  --input=evaluation/input/qa.jsonl \
  --output=evaluation/output/qa_answers.jsonl
```

## Run evaluation and red teaming

You can run the evaluation process with the following command. The provided configuration file
[evaluation/config.json](./config.json) will be used by default; feel free to edit it or provide your own.
You should specify the models you want to run evaluation on in the configuration file, with more than one
models implying a comparison between them. You can view the available models' names, as well as all options
provided by the CLI with the `--help` option. By default, the following command will run both the metrics-based
GPT evaluation and the red teaming approach.

```shell
python -m evaluation run
```

### Specify desired evaluation metrics

The evaluation script will use the metrics specified in the `requested_metrics` field of the config JSON.
Some of those metrics are built-in to the evaluation SDK, while others are custom.

#### Built-in metrics

These metrics are calculated by sending a call to the GPT model, asking it to provide a 1-5 rating, and storing that rating.

> [!IMPORTANT]
> The generator script can only generate English Q/A pairs right now, due to [limitations in the azure-ai-generative SDK](https://github.com/Azure/azure-sdk-for-python/issues/34099).

- [`gpt_coherence`](https://learn.microsoft.com/azure/ai-studio/concepts/evaluation-metrics-built-in#ai-assisted-coherence) measures how well the language model can produce output that flows smoothly, reads naturally, and resembles human-like language.
- [`gpt_relevance`](https://learn.microsoft.com/azure/ai-studio/concepts/evaluation-metrics-built-in#ai-assisted-relevance) assesses the ability of answers to capture the key points of the context.
- [`gpt_groundedness`](https://learn.microsoft.com/azure/ai-studio/concepts/evaluation-metrics-built-in#ai-assisted-groundedness) assesses the correspondence between claims in an AI-generated answer and the source context, making sure that these claims are substantiated by the context.
- [`gpt_similarity`](https://learn.microsoft.com/azure/ai-studio/concepts/evaluation-metrics-built-in#ai-assisted-gpt-similarity) measures the similarity between a source data (ground truth) sentence and the generated response by an AI model.
- [`gpt_fluency`](https://learn.microsoft.com/azure/ai-studio/concepts/evaluation-metrics-built-in#ai-assisted-fluency) measures the grammatical proficiency of a generative AI's predicted answer.
- [`f1_score`](https://learn.microsoft.com/azure/ai-studio/concepts/evaluation-metrics-built-in#traditional-machine-learning-f1-score) Measures the ratio of the number of shared words between the model generation and the ground truth answers.

### Evaluation results

The results of each evaluation run are stored in the specified results directory, in a timestamped
`experiment-XXXXXXXXXX` subdirectory that contains:

- `config.json`: The original config used for the run. This is useful for reproducing the run.
- `eval_results.jsonl`: Each question and answer, along with the GPT metrics for each QA pair.
- `evaluation_gpt_boxplot.png`: A box chart for the results of the evaluation metrics.
- `evaluation_gpt_radar.png`: A radar chart with the mean score of the evaluation metrics.
- `evaluation_results.png`: Bar charts for the pass count, pass rate and average rating of the evaluation metrics.
- `evaluation_stat_boxplot.png`: Box charts for the evaluation results corresponding to the answer length, latency,
   and F1 score.
- `summary.json`: The overall GPT evaluation results, e.g. average GPT metrics.
- `scores.json`: The results of the red teaming approach.
- `red_teaming_results.png`: A tabular visualisation of the red teaming results.
- `evaluation_report.pdf`: A PDF report containing the graphs and aggregated metrics for the completed evaluation run.
