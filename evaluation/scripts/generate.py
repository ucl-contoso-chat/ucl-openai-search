import json
import logging
from pathlib import Path

from azure.ai.generative.synthetic.qa import QADataGenerator, QAType
from azure.search.documents import SearchClient
from openai_messages_token_helper import get_token_limit

from scripts import service_setup

logger = logging.getLogger("scripts")


def generate_test_qa_data(
    openai_config: dict,
    search_client: SearchClient,
    num_questions_total: int,
    num_questions_per_source: int,
    output_file: Path,
):
    logger.info(
        "Generating %d questions total, %d per source, based on search results",
        num_questions_total,
        num_questions_per_source,
    )

    qa_generator = QADataGenerator(model_config=openai_config)

    r = search_client.search("", top=1000)
    qa: list[dict] = []
    for doc in r:
        if len(qa) > num_questions_total:
            break
        logger.info("Processing search document %s", doc["sourcepage"])
        text = doc["content"]

        result = qa_generator.generate(
            text=text,
            qa_type=QAType.LONG_ANSWER,
            num_questions=num_questions_per_source,
        )

        for question, answer in result["question_answers"]:
            citation = f"[{doc['sourcepage']}]"
            qa.append({"question": question, "truth": answer + citation})

    logger.info("Writing %d questions to %s", len(qa), output_file)
    directory = Path(output_file).parent
    if not directory.exists():
        directory.mkdir(parents=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for item in qa:
            f.write(json.dumps(item) + "\n")


def generate_test_qa_answer(
    openai_config,
    question_path: Path,
    output_file: Path,
    using_huggingface: bool = False,
):
    logger.info("Generating answers based on the quesion of %s", question_path)
    with open(question_path, encoding="utf-8") as f:
        questions = [json.loads(line) for line in f.readlines()]

    if not using_huggingface:
        logger.info("Using Azure OpenAI Service")
        openai_client = service_setup.get_openai_client(openai_config)

        for question in questions:
            response = openai_client.chat.completions.create(
                model=openai_config.model,
                messages=[
                    {
                        "role": "user",
                        "content": f"{question['question']}",
                    }
                ],
                n=1,
                max_tokens=get_token_limit(openai_config.model),
                temperature=0.3,
            )
            answer = response.choices[0].message.content.split("\n")[0]
            print(answer)
            question["answer"] = answer
    else:
        # TODO: Implement Hugging Face Service
        logger.info("Using Hugging Face Service")

    logger.info("Writing %d questions with answer to %s", len(questions), output_file)

    directory = Path(output_file).parent
    if not directory.exists():
        directory.mkdir(parents=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for item in questions:
            f.write(json.dumps(item) + "\n")
