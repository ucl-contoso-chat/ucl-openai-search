import asyncio
import dataclasses
import io
import json
import logging
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Union, cast

from azure.cognitiveservices.speech import (
    ResultReason,
    SpeechConfig,
    SpeechSynthesisOutputFormat,
    SpeechSynthesisResult,
    SpeechSynthesizer,
)
from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.storage.blob.aio import ContainerClient
from azure.storage.blob.aio import StorageStreamDownloader as BlobDownloader
from azure.storage.filedatalake.aio import FileSystemClient
from azure.storage.filedatalake.aio import StorageStreamDownloader as DatalakeDownloader
from huggingface_hub import login  # type: ignore
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.instrumentation.httpx import (
    HTTPXClientInstrumentor,
)
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from quart import (
    Blueprint,
    Quart,
    abort,
    current_app,
    jsonify,
    make_response,
    request,
    send_file,
    send_from_directory,
)
from quart_cors import cors

from api_wrappers import (
    AzureOpenAIClient,
    HuggingFaceClient,
    LLMClient,
    LocalOpenAIClient,
)
from approaches.approach import Approach
from approaches.chatreadretrieveread import ChatReadRetrieveReadApproach
from approaches.chatreadretrievereadvision import ChatReadRetrieveReadVisionApproach
from approaches.retrievethenread import RetrieveThenReadApproach
from approaches.retrievethenreadvision import RetrieveThenReadVisionApproach
from config import (
    CONFIG_ASK_APPROACH,
    CONFIG_ASK_VISION_APPROACH,
    CONFIG_AUTH_CLIENT,
    CONFIG_AVAILABLE_MODELS,
    CONFIG_BLOB_CONTAINER_CLIENT,
    CONFIG_CHAT_APPROACH,
    CONFIG_CHAT_VISION_APPROACH,
    CONFIG_CREDENTIAL,
    CONFIG_CURRENT_MODEL,
    CONFIG_GPT4V_DEPLOYED,
    CONFIG_INGESTER,
    CONFIG_LLM_CLIENTS,
    CONFIG_PROMPT_PROTECTION,
    CONFIG_SEARCH_CLIENT,
    CONFIG_SEMANTIC_RANKER_DEPLOYED,
    CONFIG_SPEECH_INPUT_ENABLED,
    CONFIG_SPEECH_OUTPUT_AZURE_ENABLED,
    CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED,
    CONFIG_SPEECH_SERVICE_ID,
    CONFIG_SPEECH_SERVICE_LOCATION,
    CONFIG_SPEECH_SERVICE_TOKEN,
    CONFIG_SPEECH_SERVICE_VOICE,
    CONFIG_USER_BLOB_CONTAINER_CLIENT,
    CONFIG_USER_UPLOAD_ENABLED,
    CONFIG_VECTOR_SEARCH_ENABLED,
)
from core.authentication import AuthenticationHelper
from core.promptprotection import PromptProtection
from decorators import authenticated, authenticated_path
from error import error_dict, error_response
from prepdocs import (
    clean_key_if_exists,
    setup_embeddings_service,
    setup_file_processors,
    setup_search_info,
)
from prepdocslib.filestrategy import UploadUserFileStrategy
from prepdocslib.listfilestrategy import File
from templates.supported_models import get_supported_models

PYRIT_COMPATIBLE = sys.version_info >= (3, 10) and sys.version_info < (3, 12)

if PYRIT_COMPATIBLE:
    from evaluation.config import get_evaluation_config, get_red_teaming_config
    from evaluation.evaluate import run_evaluation_from_config
    from evaluation.generate import generate_test_qa_data
    from evaluation.service_setup import (
        get_openai_config_dict,
        get_search_client,
    )
    from evaluation.utils import save_jsonl

    BACKEND_DIR = Path(__file__).parent
    EVALUATION_DIR = BACKEND_DIR / "evaluation"

bp = Blueprint("routes", __name__, static_folder="static")
# Fix Windows registry issue with mimetypes
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

os.environ["BACKEND_URI"] = (
    f"https://{os.getenv('WEBSITE_HOSTNAME')}" if os.getenv("WEBSITE_HOSTNAME") else "http://localhost:50505"
)


@bp.route("/")
async def index():
    return await bp.send_static_file("index.html")


# Empty page is recommended for login redirect to work.
# See https://github.com/AzureAD/microsoft-authentication-library-for-js/blob/dev/lib/msal-browser/docs/initialization.md#redirecturi-considerations for more information
@bp.route("/redirect")
async def redirect():
    return ""


@bp.route("/favicon.ico")
async def favicon():
    return await bp.send_static_file("favicon.ico")


@bp.route("/assets/<path:path>")
async def assets(path):
    return await send_from_directory(Path(__file__).resolve().parent / "static" / "assets", path)


@bp.route("/content/<path>")
@authenticated_path
async def content_file(path: str, auth_claims: Dict[str, Any]):
    """
    Serve content files from blob storage from within the app to keep the example self-contained.
    *** NOTE *** if you are using app services authentication, this route will return unauthorized to all users that are not logged in
    if AZURE_ENFORCE_ACCESS_CONTROL is not set or false, logged in users can access all files regardless of access control
    if AZURE_ENFORCE_ACCESS_CONTROL is set to true, logged in users can only access files they have access to
    This is also slow and memory hungry.
    """
    # Remove page number from path, filename-1.txt -> filename.txt
    # This shouldn't typically be necessary as browsers don't send hash fragments to servers
    if path.find("#page=") > 0:
        path_parts = path.rsplit("#page=", 1)
        path = path_parts[0]
    logging.info("Opening file %s", path)
    blob_container_client: ContainerClient = current_app.config[CONFIG_BLOB_CONTAINER_CLIENT]
    blob: Union[BlobDownloader, DatalakeDownloader]
    try:
        blob = await blob_container_client.get_blob_client(path).download_blob()
    except ResourceNotFoundError:
        logging.info("Path not found in general Blob container: %s", path)
        if current_app.config[CONFIG_USER_UPLOAD_ENABLED]:
            try:
                user_oid = auth_claims["oid"]
                user_blob_container_client = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
                user_directory_client: FileSystemClient = user_blob_container_client.get_directory_client(user_oid)
                file_client = user_directory_client.get_file_client(path)
                blob = await file_client.download_file()
            except ResourceNotFoundError:
                logging.exception("Path not found in DataLake: %s", path)
                abort(404)
        else:
            abort(404)
    if not blob.properties or not blob.properties.has_key("content_settings"):
        abort(404)
    mime_type = blob.properties["content_settings"]["content_type"]
    if mime_type == "application/octet-stream":
        mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    blob_file = io.BytesIO()
    await blob.readinto(blob_file)
    blob_file.seek(0)
    return await send_file(blob_file, mimetype=mime_type, as_attachment=False, attachment_filename=path)


@bp.route("/ask", methods=["POST"])
@authenticated
async def ask(auth_claims: Dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    context["auth_claims"] = auth_claims
    try:
        use_gpt4v = context.get("overrides", {}).get("use_gpt4v", False)
        approach: Approach
        if use_gpt4v and CONFIG_ASK_VISION_APPROACH in current_app.config:
            approach = cast(Approach, current_app.config[CONFIG_ASK_VISION_APPROACH])
        else:
            approach = cast(Approach, current_app.config[CONFIG_ASK_APPROACH])
        r = await approach.run(
            request_json["messages"], context=context, session_state=request_json.get("session_state")
        )
        return jsonify(r)
    except Exception as error:
        return error_response(error, "/ask")


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        return super().default(o)


async def format_as_ndjson(r: AsyncGenerator[dict, None]) -> AsyncGenerator[str, None]:
    try:
        async for event in r:
            yield json.dumps(event, ensure_ascii=False, cls=JSONEncoder) + "\n"
    except Exception as error:
        logging.exception("Exception while generating response stream: %s", error)
        yield json.dumps(error_dict(error))


@bp.route("/chat", methods=["POST"])
@authenticated
async def chat(auth_claims: Dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    context["auth_claims"] = auth_claims
    try:
        use_gpt4v = context.get("overrides", {}).get("use_gpt4v", False)
        approach: Approach
        if use_gpt4v and CONFIG_CHAT_VISION_APPROACH in current_app.config:
            approach = cast(Approach, current_app.config[CONFIG_CHAT_VISION_APPROACH])
        else:
            approach = cast(Approach, current_app.config[CONFIG_CHAT_APPROACH])

        result = await approach.run(
            request_json["messages"],
            context=context,
            session_state=request_json.get("session_state"),
        )
        return jsonify(result)
    except Exception as error:
        return error_response(error, "/chat")


@bp.route("/chat/stream", methods=["POST"])
@authenticated
async def chat_stream(auth_claims: Dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    context = request_json.get("context", {})
    context["auth_claims"] = auth_claims
    try:
        use_gpt4v = context.get("overrides", {}).get("use_gpt4v", False)
        approach: Approach
        if use_gpt4v and CONFIG_CHAT_VISION_APPROACH in current_app.config:
            approach = cast(Approach, current_app.config[CONFIG_CHAT_VISION_APPROACH])
        else:
            approach = cast(Approach, current_app.config[CONFIG_CHAT_APPROACH])

        result = await approach.run_stream(
            request_json["messages"],
            context=context,
            session_state=request_json.get("session_state"),
        )
        response = await make_response(format_as_ndjson(result))
        response.timeout = None  # type: ignore
        response.mimetype = "application/json-lines"
        return response
    except Exception as error:
        return error_response(error, "/chat")


# Send MSAL.js settings to the client UI
@bp.route("/auth_setup", methods=["GET"])
def auth_setup():
    auth_helper = current_app.config[CONFIG_AUTH_CLIENT]
    return jsonify(auth_helper.get_auth_setup_for_client())


@bp.route("/config", methods=["GET"])
def config():
    return jsonify(
        {
            "showGPT4VOptions": current_app.config[CONFIG_GPT4V_DEPLOYED],
            "showSemanticRankerOption": current_app.config[CONFIG_SEMANTIC_RANKER_DEPLOYED],
            "showVectorOption": current_app.config[CONFIG_VECTOR_SEARCH_ENABLED],
            "showUserUpload": current_app.config[CONFIG_USER_UPLOAD_ENABLED],
            "showSpeechInput": current_app.config[CONFIG_SPEECH_INPUT_ENABLED],
            "showSpeechOutputBrowser": current_app.config[CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED],
            "showSpeechOutputAzure": current_app.config[CONFIG_SPEECH_OUTPUT_AZURE_ENABLED],
            "currentModel": current_app.config[CONFIG_CURRENT_MODEL],
            "protectionConfig": current_app.config[CONFIG_PROMPT_PROTECTION],
        }
    )


@bp.route("/getmodels", methods=["GET"])
def getmodels():
    model_names: List[str] = []
    for model_name in current_app.config[CONFIG_AVAILABLE_MODELS].keys():
        model_names.append(model_name)
    return jsonify(model_names)


@bp.route("/speech", methods=["POST"])
async def speech():
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415

    speech_token = current_app.config.get(CONFIG_SPEECH_SERVICE_TOKEN)
    if speech_token is None or speech_token.expires_on < time.time() + 60:
        speech_token = await current_app.config[CONFIG_CREDENTIAL].get_token(
            "https://cognitiveservices.azure.com/.default"
        )
        current_app.config[CONFIG_SPEECH_SERVICE_TOKEN] = speech_token

    request_json = await request.get_json()
    text = request_json["text"]
    try:
        # Construct a token as described in documentation:
        # https://learn.microsoft.com/azure/ai-services/speech-service/how-to-configure-azure-ad-auth?pivots=programming-language-python
        auth_token = (
            "aad#"
            + current_app.config[CONFIG_SPEECH_SERVICE_ID]
            + "#"
            + current_app.config[CONFIG_SPEECH_SERVICE_TOKEN].token
        )
        speech_config = SpeechConfig(auth_token=auth_token, region=current_app.config[CONFIG_SPEECH_SERVICE_LOCATION])
        speech_config.speech_synthesis_voice_name = current_app.config[CONFIG_SPEECH_SERVICE_VOICE]
        speech_config.speech_synthesis_output_format = SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        result: SpeechSynthesisResult = synthesizer.speak_text_async(text).get()
        if result.reason == ResultReason.SynthesizingAudioCompleted:
            return result.audio_data, 200, {"Content-Type": "audio/mp3"}
        elif result.reason == ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            current_app.logger.error(
                "Speech synthesis canceled: %s %s", cancellation_details.reason, cancellation_details.error_details
            )
            raise Exception("Speech synthesis canceled. Check logs for details.")
        else:
            current_app.logger.error("Unexpected result reason: %s", result.reason)
            raise Exception("Speech synthesis failed. Check logs for details.")
    except Exception as e:
        logging.exception("Exception in /speech")
        return jsonify({"error": str(e)}), 500


if PYRIT_COMPATIBLE:

    @bp.route("/evaluate", methods=["POST"])
    @authenticated
    async def evaluate(auth_claims: dict[str, Any]):
        request_form = await request.form
        request_files = await request.files
        if "input_data" not in request_files:
            return jsonify({"message": "No input_data part in the request", "status": "failed"}), 400
        if "config" not in request_form:
            return jsonify({"message": "No application setting config part in the request", "status": "failed"}), 400

        input_data_file = request_files.get("input_data")
        num_questions_str = request_form.get("num_questions", "")
        num_questions = None if num_questions_str == "" else int(num_questions_str)
        config = json.loads(request_form.get("config", "{}"))

        if input_data_file is not None:
            input_data = [json.loads(line) for line in input_data_file.readlines()]
        save_jsonl(input_data, Path("./evaluation/input/input_temp.jsonl"))
        config["testdata_path"] = "input/input_temp.jsonl"
        config["results_dir"] = "results"
        config["scorer_dir"] = "scorer_definitions"
        config["prompt_target"] = "application"

        evaluation_config = get_evaluation_config(
            enabled=config.get("run_evaluation", True),
            num_questions=num_questions,
            target_url=config.get("target_url"),
        )
        red_teaming_config = get_red_teaming_config(
            enabled=config.get("run_red_teaming", True),
            scorer_dir=Path(config.get("scorer_dir")),
            prompt_target=config.get("prompt_target"),
            max_turns=config.get("red_teaming_max_turns"),
            config=config,
            target_url=config.get("target_url"),
        )

        evaluation_task = asyncio.create_task(
            run_evaluation_from_config(
                working_dir=EVALUATION_DIR,
                config=config,
                evaluation_config=evaluation_config,
                red_teaming_config=red_teaming_config,
            )
        )

        while not evaluation_task.done():
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                evaluation_task.cancel()
                return jsonify({"error": "Connection Lost, evaluation task was cancelled"}), 500

        report_path = await evaluation_task

        # if evaluation failed
        if not report_path:
            evaluation_task.cancel()
            return jsonify({"error": "Evaluation was terminated early due to an error"}), 500

        try:
            return_data = io.BytesIO()
            with open(report_path, "rb") as fo:
                return_data.write(fo.read())
            return_data.seek(0)
            result = await send_file(return_data, as_attachment=True, mimetype="application/pdf")
            return result
        except Exception:
            return jsonify({"error": "Failed while writing the report file"}), 500


@bp.route("/generate", methods=["POST"])
@authenticated
async def generate_qa(auth_claims: dict[str, Any]):
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()

    num_questions = request_json.get("num_questions")
    per_source = request_json.get("per_source")
    output_file = EVALUATION_DIR / "input" / "input_temp.jsonl"

    generate_test_qa_data(
        openai_config=get_openai_config_dict(),
        search_client=get_search_client(),
        num_questions_total=num_questions,
        num_questions_per_source=per_source,
        output_file=output_file,
    )

    try:
        # Save the file in memory and remove the original file
        return_data = io.BytesIO()
        with open(output_file, "rb") as fo:
            return_data.write(fo.read())
        return_data.seek(0)
        os.remove(output_file)
        result = await send_file(return_data, as_attachment=True, mimetype="application/jsonl")
        return result
    except Exception as e:
        os.remove(output_file)
        return error_response(e, "/generate")


@bp.post("/upload")
@authenticated
async def upload(auth_claims: dict[str, Any]):
    request_files = await request.files
    if "file" not in request_files:
        # If no files were included in the request, return an error response
        return jsonify({"message": "No file part in the request", "status": "failed"}), 400

    user_oid = auth_claims["oid"]
    file = request_files.getlist("file")[0]
    user_blob_container_client: FileSystemClient = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
    user_directory_client = user_blob_container_client.get_directory_client(user_oid)
    try:
        await user_directory_client.get_directory_properties()
    except ResourceNotFoundError:
        current_app.logger.info("Creating directory for user %s", user_oid)
        await user_directory_client.create_directory()
    await user_directory_client.set_access_control(owner=user_oid)
    file_client = user_directory_client.get_file_client(file.filename)
    file_io = file
    file_io.name = file.filename
    file_io = io.BufferedReader(file_io)
    await file_client.upload_data(file_io, overwrite=True, metadata={"UploadedBy": user_oid})
    file_io.seek(0)
    ingester: UploadUserFileStrategy = current_app.config[CONFIG_INGESTER]
    await ingester.add_file(File(content=file_io, acls={"oids": [user_oid]}, url=file_client.url))
    return jsonify({"message": "File uploaded successfully"}), 200


@bp.post("/delete_uploaded")
@authenticated
async def delete_uploaded(auth_claims: dict[str, Any]):
    request_json = await request.get_json()
    filename = request_json.get("filename")
    user_oid = auth_claims["oid"]
    user_blob_container_client: FileSystemClient = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
    user_directory_client = user_blob_container_client.get_directory_client(user_oid)
    file_client = user_directory_client.get_file_client(filename)
    await file_client.delete_file()
    ingester = current_app.config[CONFIG_INGESTER]
    await ingester.remove_file(filename, user_oid)
    return jsonify({"message": f"File {filename} deleted successfully"}), 200


@bp.get("/list_uploaded")
@authenticated
async def list_uploaded(auth_claims: dict[str, Any]):
    user_oid = auth_claims["oid"]
    user_blob_container_client: FileSystemClient = current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT]
    files = []
    try:
        all_paths = user_blob_container_client.get_paths(path=user_oid)
        async for path in all_paths:
            files.append(path.name.split("/", 1)[1])
    except ResourceNotFoundError as error:
        if error.status_code != 404:
            current_app.logger.exception("Error listing uploaded files", error)
    return jsonify(files), 200


@bp.before_app_serving
async def setup_clients():
    # Replace these with your own values, either in environment variables or directly here
    AZURE_STORAGE_ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]
    AZURE_STORAGE_CONTAINER = os.environ["AZURE_STORAGE_CONTAINER"]
    AZURE_USERSTORAGE_ACCOUNT = os.environ.get("AZURE_USERSTORAGE_ACCOUNT")
    AZURE_USERSTORAGE_CONTAINER = os.environ.get("AZURE_USERSTORAGE_CONTAINER")
    AZURE_SEARCH_SERVICE = os.environ["AZURE_SEARCH_SERVICE"]
    AZURE_SEARCH_INDEX = os.environ["AZURE_SEARCH_INDEX"]
    # Shared by all OpenAI deployments
    OPENAI_HOST = os.getenv("OPENAI_HOST", "azure")
    OPENAI_CHATGPT_MODEL = os.environ["AZURE_OPENAI_CHATGPT_MODEL"]
    OPENAI_EMB_MODEL = os.getenv("AZURE_OPENAI_EMB_MODEL_NAME", "text-embedding-ada-002")
    OPENAI_EMB_DIMENSIONS = int(os.getenv("AZURE_OPENAI_EMB_DIMENSIONS", 1536))

    # Used with Azure OpenAI deployments
    AZURE_OPENAI_SERVICE = os.getenv("AZURE_OPENAI_SERVICE")
    AZURE_OPENAI_GPT4V_DEPLOYMENT = os.environ.get("AZURE_OPENAI_GPT4V_DEPLOYMENT")
    AZURE_OPENAI_GPT4V_MODEL = os.environ.get("AZURE_OPENAI_GPT4V_MODEL")
    AZURE_OPENAI_CHATGPT_DEPLOYMENT = (
        os.getenv("AZURE_OPENAI_CHATGPT_DEPLOYMENT") if OPENAI_HOST.startswith("azure") else None
    )
    AZURE_OPENAI_EMB_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMB_DEPLOYMENT") if OPENAI_HOST.startswith("azure") else None
    AZURE_OPENAI_CUSTOM_URL = os.getenv("AZURE_OPENAI_CUSTOM_URL")
    AZURE_VISION_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT", "")
    # Used only with non-Azure OpenAI deployments
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_ORGANIZATION = os.getenv("OPENAI_ORGANIZATION")

    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
    AZURE_USE_AUTHENTICATION = os.getenv("AZURE_USE_AUTHENTICATION", "").lower() == "true"
    AZURE_ENFORCE_ACCESS_CONTROL = os.getenv("AZURE_ENFORCE_ACCESS_CONTROL", "").lower() == "true"
    AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS = os.getenv("AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS", "").lower() == "true"
    AZURE_ENABLE_UNAUTHENTICATED_ACCESS = os.getenv("AZURE_ENABLE_UNAUTHENTICATED_ACCESS", "").lower() == "true"
    AZURE_SERVER_APP_ID = os.getenv("AZURE_SERVER_APP_ID")
    AZURE_SERVER_APP_SECRET = os.getenv("AZURE_SERVER_APP_SECRET")
    AZURE_CLIENT_APP_ID = os.getenv("AZURE_CLIENT_APP_ID")
    AZURE_AUTH_TENANT_ID = os.getenv("AZURE_AUTH_TENANT_ID", AZURE_TENANT_ID)

    KB_FIELDS_CONTENT = os.getenv("KB_FIELDS_CONTENT", "content")
    KB_FIELDS_SOURCEPAGE = os.getenv("KB_FIELDS_SOURCEPAGE", "sourcepage")

    AZURE_SEARCH_QUERY_LANGUAGE = os.getenv("AZURE_SEARCH_QUERY_LANGUAGE", "en-us")
    AZURE_SEARCH_QUERY_SPELLER = os.getenv("AZURE_SEARCH_QUERY_SPELLER", "lexicon")
    AZURE_SEARCH_SEMANTIC_RANKER = os.getenv("AZURE_SEARCH_SEMANTIC_RANKER", "free").lower()

    AZURE_SPEECH_SERVICE_ID = os.getenv("AZURE_SPEECH_SERVICE_ID")
    AZURE_SPEECH_SERVICE_LOCATION = os.getenv("AZURE_SPEECH_SERVICE_LOCATION")
    AZURE_SPEECH_VOICE = os.getenv("AZURE_SPEECH_VOICE", "en-US-AndrewMultilingualNeural")

    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL")

    USE_INJECTION_PROTECTION = os.getenv("USE_INJECTION_PROTECTION", "").lower() == "true"

    USE_GPT4V = os.getenv("USE_GPT4V", "").lower() == "true"
    USE_USER_UPLOAD = os.getenv("USE_USER_UPLOAD", "").lower() == "true"
    USE_SPEECH_INPUT_BROWSER = os.getenv("USE_SPEECH_INPUT_BROWSER", "").lower() == "true"
    USE_SPEECH_OUTPUT_BROWSER = os.getenv("USE_SPEECH_OUTPUT_BROWSER", "").lower() == "true"
    USE_SPEECH_OUTPUT_AZURE = os.getenv("USE_SPEECH_OUTPUT_AZURE", "").lower() == "true"

    # Use the current user identity to authenticate with Azure OpenAI, AI Search and Blob Storage (no secrets needed,
    # just use 'az login' locally, and managed identity when deployed on Azure). If you need to use keys, use separate AzureKeyCredential instances with the
    # keys for each service
    # If you encounter a blocking error during a DefaultAzureCredential resolution, you can exclude the problematic credential by using a parameter (ex. exclude_shared_token_cache_credential=True)
    azure_credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)

    # Set up clients for AI Search and Storage
    search_client = SearchClient(
        endpoint=f"https://{AZURE_SEARCH_SERVICE}.search.windows.net",
        index_name=AZURE_SEARCH_INDEX,
        credential=azure_credential,
    )

    blob_container_client = ContainerClient(
        f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net", AZURE_STORAGE_CONTAINER, credential=azure_credential
    )

    # Set up authentication helper
    search_index = None
    if AZURE_USE_AUTHENTICATION:
        search_index_client = SearchIndexClient(
            endpoint=f"https://{AZURE_SEARCH_SERVICE}.search.windows.net",
            credential=azure_credential,
        )
        search_index = await search_index_client.get_index(AZURE_SEARCH_INDEX)
        await search_index_client.close()
    auth_helper = AuthenticationHelper(
        search_index=search_index,
        use_authentication=AZURE_USE_AUTHENTICATION,
        server_app_id=AZURE_SERVER_APP_ID,
        server_app_secret=AZURE_SERVER_APP_SECRET,
        client_app_id=AZURE_CLIENT_APP_ID,
        tenant_id=AZURE_AUTH_TENANT_ID,
        require_access_control=AZURE_ENFORCE_ACCESS_CONTROL,
        enable_global_documents=AZURE_ENABLE_GLOBAL_DOCUMENT_ACCESS,
        enable_unauthenticated_access=AZURE_ENABLE_UNAUTHENTICATED_ACCESS,
    )

    if USE_USER_UPLOAD:
        current_app.logger.info("USE_USER_UPLOAD is true, setting up user upload feature")
        if not AZURE_USERSTORAGE_ACCOUNT or not AZURE_USERSTORAGE_CONTAINER:
            raise ValueError(
                "AZURE_USERSTORAGE_ACCOUNT and AZURE_USERSTORAGE_CONTAINER must be set when USE_USER_UPLOAD is true"
            )
        user_blob_container_client = FileSystemClient(
            f"https://{AZURE_USERSTORAGE_ACCOUNT}.dfs.core.windows.net",
            AZURE_USERSTORAGE_CONTAINER,
            credential=azure_credential,
        )
        current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT] = user_blob_container_client

        # Set up ingester
        file_processors = setup_file_processors(
            azure_credential=azure_credential,
            document_intelligence_service=os.getenv("AZURE_DOCUMENTINTELLIGENCE_SERVICE"),
            local_pdf_parser=os.getenv("USE_LOCAL_PDF_PARSER", "").lower() == "true",
            local_html_parser=os.getenv("USE_LOCAL_HTML_PARSER", "").lower() == "true",
            search_images=USE_GPT4V,
        )
        search_info = await setup_search_info(
            search_service=AZURE_SEARCH_SERVICE, index_name=AZURE_SEARCH_INDEX, azure_credential=azure_credential
        )
        text_embeddings_service = setup_embeddings_service(
            azure_credential=azure_credential,
            openai_host=OPENAI_HOST,
            openai_model_name=OPENAI_EMB_MODEL,
            openai_service=AZURE_OPENAI_SERVICE,
            openai_custom_url=AZURE_OPENAI_CUSTOM_URL,
            openai_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
            openai_dimensions=OPENAI_EMB_DIMENSIONS,
            openai_key=clean_key_if_exists(OPENAI_API_KEY),
            openai_org=OPENAI_ORGANIZATION,
            disable_vectors=os.getenv("USE_VECTORS", "").lower() == "false",
        )
        ingester = UploadUserFileStrategy(
            search_info=search_info, embeddings=text_embeddings_service, file_processors=file_processors
        )
        current_app.config[CONFIG_INGESTER] = ingester

    # Used by the OpenAI SDK
    hf_client: LLMClient
    openai_client: LLMClient

    if USE_SPEECH_OUTPUT_AZURE:
        if not AZURE_SPEECH_SERVICE_ID or AZURE_SPEECH_SERVICE_ID == "":
            raise ValueError("Azure speech resource not configured correctly, missing AZURE_SPEECH_SERVICE_ID")
        if not AZURE_SPEECH_SERVICE_LOCATION or AZURE_SPEECH_SERVICE_LOCATION == "":
            raise ValueError("Azure speech resource not configured correctly, missing AZURE_SPEECH_SERVICE_LOCATION")
        current_app.config[CONFIG_SPEECH_SERVICE_ID] = AZURE_SPEECH_SERVICE_ID
        current_app.config[CONFIG_SPEECH_SERVICE_LOCATION] = AZURE_SPEECH_SERVICE_LOCATION
        current_app.config[CONFIG_SPEECH_SERVICE_VOICE] = AZURE_SPEECH_VOICE
        # Wait until token is needed to fetch for the first time
        current_app.config[CONFIG_SPEECH_SERVICE_TOKEN] = None
        current_app.config[CONFIG_CREDENTIAL] = azure_credential
    if OPENAI_HOST.startswith("azure"):
        api_version = os.getenv("AZURE_OPENAI_API_VERSION") or "2024-03-01-preview"
        if OPENAI_HOST == "azure_custom":
            if not AZURE_OPENAI_CUSTOM_URL:
                raise ValueError("AZURE_OPENAI_CUSTOM_URL must be set when OPENAI_HOST is azure_custom")
            endpoint = AZURE_OPENAI_CUSTOM_URL
        else:
            if not AZURE_OPENAI_SERVICE:
                raise ValueError("AZURE_OPENAI_SERVICE must be set when OPENAI_HOST is azure")
            endpoint = f"https://{AZURE_OPENAI_SERVICE}.openai.azure.com"
        if api_key := os.getenv("AZURE_OPENAI_API_KEY"):
            openai_client = AzureOpenAIClient(api_version=api_version, azure_endpoint=endpoint, api_key=api_key)
        else:
            token_provider = get_bearer_token_provider(azure_credential, "https://cognitiveservices.azure.com/.default")
            openai_client = AzureOpenAIClient(
                api_version=api_version,
                azure_endpoint=endpoint,
                azure_ad_token_provider=token_provider,
            )
    elif OPENAI_HOST == "local":
        openai_client = LocalOpenAIClient(
            base_url=os.environ["OPENAI_BASE_URL"],
            api_key="no-key-required",
        )
    else:
        openai_client = LocalOpenAIClient(
            api_key=OPENAI_API_KEY,
            organization=OPENAI_ORGANIZATION,
        )

    emb_client = openai_client
    current_model: str

    # TODO: Add vision-ready models
    deployment_information = {
        "type": "azure" if AZURE_OPENAI_CHATGPT_DEPLOYMENT else "openai",
        "model_name": OPENAI_CHATGPT_MODEL,
        "deployment_name": AZURE_OPENAI_CHATGPT_DEPLOYMENT,
    }
    available_models = get_supported_models(deployment_information)

    current_model = list(available_models.keys())[0] if DEFAULT_MODEL is None else DEFAULT_MODEL
    if current_model and current_model not in available_models.keys():
        raise ValueError(
            f"DEFAULT_MODEL must be set to a supported model from\
                         {available_models.keys()}.\nCurrent model is set to {current_model}"
        )

    if not HUGGINGFACE_API_KEY:
        raise ValueError("HUGGINGFACE_API_KEY must be set if you want to use full capabilities.")
    else:
        login(token=HUGGINGFACE_API_KEY)
        hf_client = HuggingFaceClient(token=HUGGINGFACE_API_KEY)

    llm_clients: dict[str, LLMClient] = {"openai": openai_client, "hf": hf_client}

    prompt_protection = PromptProtection(injection_protection_enabled=USE_INJECTION_PROTECTION)

    current_app.config[CONFIG_LLM_CLIENTS] = llm_clients
    current_app.config[CONFIG_SEARCH_CLIENT] = search_client
    current_app.config[CONFIG_CURRENT_MODEL] = current_model
    current_app.config[CONFIG_PROMPT_PROTECTION] = prompt_protection.protections
    current_app.config[CONFIG_AVAILABLE_MODELS] = available_models
    current_app.config[CONFIG_BLOB_CONTAINER_CLIENT] = blob_container_client
    current_app.config[CONFIG_AUTH_CLIENT] = auth_helper
    current_app.config[CONFIG_GPT4V_DEPLOYED] = bool(USE_GPT4V)
    current_app.config[CONFIG_SEMANTIC_RANKER_DEPLOYED] = AZURE_SEARCH_SEMANTIC_RANKER != "disabled"
    current_app.config[CONFIG_VECTOR_SEARCH_ENABLED] = os.getenv("USE_VECTORS", "").lower() != "false"
    current_app.config[CONFIG_USER_UPLOAD_ENABLED] = bool(USE_USER_UPLOAD)
    current_app.config[CONFIG_SPEECH_INPUT_ENABLED] = USE_SPEECH_INPUT_BROWSER
    current_app.config[CONFIG_SPEECH_OUTPUT_BROWSER_ENABLED] = USE_SPEECH_OUTPUT_BROWSER
    current_app.config[CONFIG_SPEECH_OUTPUT_AZURE_ENABLED] = USE_SPEECH_OUTPUT_AZURE

    # Various approaches to integrate GPT and external knowledge, most applications will use a single one of these patterns
    # or some derivative, here we include several for exploration purposes
    current_app.config[CONFIG_ASK_APPROACH] = RetrieveThenReadApproach(
        search_client=search_client,
        llm_clients=llm_clients,
        emb_client=emb_client,
        auth_helper=auth_helper,
        current_model=current_model,
        available_models=available_models,
        prompt_protection=prompt_protection,
        embedding_model=OPENAI_EMB_MODEL,
        embedding_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
        embedding_dimensions=OPENAI_EMB_DIMENSIONS,
        sourcepage_field=KB_FIELDS_SOURCEPAGE,
        content_field=KB_FIELDS_CONTENT,
        query_language=AZURE_SEARCH_QUERY_LANGUAGE,
        query_speller=AZURE_SEARCH_QUERY_SPELLER,
    )
    current_app.config[CONFIG_CHAT_APPROACH] = ChatReadRetrieveReadApproach(
        search_client=search_client,
        llm_clients=llm_clients,
        emb_client=emb_client,
        auth_helper=auth_helper,
        current_model=current_model,
        available_models=available_models,
        prompt_protection=prompt_protection,
        embedding_model=OPENAI_EMB_MODEL,
        embedding_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
        embedding_dimensions=OPENAI_EMB_DIMENSIONS,
        sourcepage_field=KB_FIELDS_SOURCEPAGE,
        content_field=KB_FIELDS_CONTENT,
        query_language=AZURE_SEARCH_QUERY_LANGUAGE,
        query_speller=AZURE_SEARCH_QUERY_SPELLER,
    )

    if USE_GPT4V:
        current_app.logger.info("USE_GPT4V is true, setting up GPT4V approach")
        if not AZURE_OPENAI_GPT4V_MODEL:
            raise ValueError("AZURE_OPENAI_GPT4V_MODEL must be set when USE_GPT4V is true")
        token_provider = get_bearer_token_provider(azure_credential, "https://cognitiveservices.azure.com/.default")

        current_app.config[CONFIG_ASK_VISION_APPROACH] = RetrieveThenReadVisionApproach(
            search_client=search_client,
            llm_clients=llm_clients,
            emb_client=emb_client,
            blob_container_client=blob_container_client,
            auth_helper=auth_helper,
            vision_endpoint=AZURE_VISION_ENDPOINT,
            vision_token_provider=token_provider,
            current_model=current_model,
            available_models=available_models,
            gpt4v_deployment=AZURE_OPENAI_GPT4V_DEPLOYMENT,
            gpt4v_model=AZURE_OPENAI_GPT4V_MODEL,
            embedding_model=OPENAI_EMB_MODEL,
            embedding_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
            embedding_dimensions=OPENAI_EMB_DIMENSIONS,
            sourcepage_field=KB_FIELDS_SOURCEPAGE,
            content_field=KB_FIELDS_CONTENT,
            query_language=AZURE_SEARCH_QUERY_LANGUAGE,
            query_speller=AZURE_SEARCH_QUERY_SPELLER,
        )

        current_app.config[CONFIG_CHAT_VISION_APPROACH] = ChatReadRetrieveReadVisionApproach(
            search_client=search_client,
            llm_clients=llm_clients,
            emb_client=emb_client,
            blob_container_client=blob_container_client,
            auth_helper=auth_helper,
            vision_endpoint=AZURE_VISION_ENDPOINT,
            vision_token_provider=token_provider,
            current_model=current_model,
            available_models=available_models,
            gpt4v_deployment=AZURE_OPENAI_GPT4V_DEPLOYMENT,
            gpt4v_model=AZURE_OPENAI_GPT4V_MODEL,
            embedding_model=OPENAI_EMB_MODEL,
            embedding_deployment=AZURE_OPENAI_EMB_DEPLOYMENT,
            embedding_dimensions=OPENAI_EMB_DIMENSIONS,
            sourcepage_field=KB_FIELDS_SOURCEPAGE,
            content_field=KB_FIELDS_CONTENT,
            query_language=AZURE_SEARCH_QUERY_LANGUAGE,
            query_speller=AZURE_SEARCH_QUERY_SPELLER,
        )


@bp.after_app_serving
async def close_clients():
    await current_app.config[CONFIG_SEARCH_CLIENT].close()
    await current_app.config[CONFIG_BLOB_CONTAINER_CLIENT].close()
    if current_app.config.get(CONFIG_USER_BLOB_CONTAINER_CLIENT):
        await current_app.config[CONFIG_USER_BLOB_CONTAINER_CLIENT].close()


def create_app():
    app = Quart(__name__)
    app.register_blueprint(bp)

    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        configure_azure_monitor()
        # This tracks HTTP requests made by aiohttp:
        AioHttpClientInstrumentor().instrument()
        # This tracks HTTP requests made by httpx:
        HTTPXClientInstrumentor().instrument()
        # This tracks OpenAI SDK requests:
        OpenAIInstrumentor().instrument()
        # This middleware tracks app route requests:
        app.asgi_app = OpenTelemetryMiddleware(app.asgi_app)  # type: ignore[assignment]

    # Level should be one of https://docs.python.org/3/library/logging.html#logging-levels
    default_level = "INFO"  # In development, log more verbosely
    if os.getenv("WEBSITE_HOSTNAME"):  # In production, don't log as heavily
        default_level = "WARNING"
    logging.basicConfig(level=os.getenv("APP_LOG_LEVEL", default_level))

    if allowed_origin := os.getenv("ALLOWED_ORIGIN"):
        app.logger.info("CORS enabled for %s", allowed_origin)
        cors(app, allow_origin=allowed_origin, allow_methods=["GET", "POST"])
    return app
