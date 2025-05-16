import boto3
import re
import json
from retrying import retry
from botocore.config import Config
from botocore.exceptions import ClientError
from collections import defaultdict
from pydantic import BaseModel

CLAUDE_SMALL_MODEL_ID = "us.anthropic.claude-3-haiku-20240307-v1:0"
CLAUDE_SMALL_MODEL_ID_V2 = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
CLAUDE_LARGE_MODEL_ID = "us.anthropic.claude-3-5-sonnet-20240620-v1:0"
CLAUDE_LARGE_MODEL_ID_V2 = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
CLAUDE_REASONING_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

DEFAULT_MODEL_ID = CLAUDE_REASONING_MODEL_ID

bedrock = boto3.client('bedrock')

# To change the region, set the AWS_DEFAULT_REGION environment variable. Example:
#       export AWS_DEFAULT_REGION=us-west-2
bedrock_runtime = boto3.client('bedrock-runtime', config=Config(
    connect_timeout=180,
    read_timeout=180,
    retries={
        "max_attempts": 50,
        "mode": "adaptive",
    },
))


class BedrockRetryableError(Exception):
    pass


def generate_prompt(prompt_template, inputs):
    return prompt_template.format_map(defaultdict(str, **inputs))


class LLMResponse(BaseModel):
    output: str
    reasoning: str | None = None
    usage: dict | None = None
    stop_reason: str | None = None


@retry(
    wait_fixed=10000,
    stop_max_attempt_number=None,
    retry_on_exception=lambda ex: isinstance(ex, BedrockRetryableError),
)
def __invoke_llm(
        messages: list,
        system_prompts=[],
        temperature=None,
        top_k=None,
        top_p=None,
        max_new_tokens=4096,
        model_id=DEFAULT_MODEL_ID,
        reasoning_enabled: bool = False,
        reasoning_tokens=1024,
        verbose=False,
) -> LLMResponse:
    if verbose:
        for i, message in enumerate(messages):
            print(f">>> Message {i + 1}:")
            print(f">>> Role: {message['role']}")

            for content_item in message['content']:
                if 'text' in content_item:
                    print(f">>> Content: {content_item['text']}")
            print(f"{'' * 50}")

        # print(f">>> Messages:\n{messages}")

    inference_config = {
        "stopSequences": ["\n\nHuman:"],
        "maxTokens": max_new_tokens,
    }

    additional_model_fields = {}

    if reasoning_enabled:
        # https://community.aws/content/2tWvN7GNtVuBco4fNgLuowHas2c/how-to-use-reasoning-with-claude-3-7-sonnet-on-amazon-bedrock-python-edition

        additional_model_fields["thinking"] = {
            "type": "enabled",
            "budget_tokens": reasoning_tokens
        }
    else:
        if temperature is not None:
            inference_config["temperature"] = temperature
        if top_p is not None:
            inference_config["topP"] = top_p
        if top_k is not None:
            additional_model_fields["top_k"] = top_k

    try:
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=messages,
            system=system_prompts,
            inferenceConfig=inference_config,
            additionalModelRequestFields=additional_model_fields,
        )

    except ClientError as exc:
        print(f"Bedrock ClientError: {exc}")

        if exc.response["Error"]["Code"] == "ThrottlingException":
            print("Bedrock throttling. To try again")
            raise BedrockRetryableError(str(exc))
        elif exc.response["Error"]["Code"] == "ModelTimeoutException":
            print("Bedrock ModelTimeoutException. To try again")
            raise BedrockRetryableError(str(exc))
        else:
            raise
    except bedrock_runtime.exceptions.ThrottlingException as throttlingExc:
        print("Bedrock ThrottlingException. To try again")
        raise BedrockRetryableError(str(throttlingExc))
    except bedrock_runtime.exceptions.ModelTimeoutException as timeoutExc:
        print("Bedrock ModelTimeoutException. To try again")
        raise BedrockRetryableError(str(timeoutExc))

    content_blocks = response["output"]["message"]["content"]
    reasoning = ""
    output = ""
    for block in content_blocks:
        if "reasoningContent" in block:
            reasoning = block["reasoningContent"]["reasoningText"]["text"]
        if "text" in block:
            output = block["text"]

    if verbose:
        print(f"Model reasoning:\n{reasoning}", flush=True)
        print(f"Model response: {output}", flush=True)
        print(f"Model usage: {response['usage']}", flush=True)
        print(f"Model stop_reason: {response['stopReason']}", flush=True)

    llm_response = LLMResponse(
        output=output,
        reasoning=reasoning,
        usage=response['usage'],
        stop_reason=response['stopReason']
    )

    return llm_response


def invoke_llm(prompt: str, document_content=None, document_format=None, temperature=None, top_k=None, top_p=None,
               max_new_tokens=4096, model_id=DEFAULT_MODEL_ID, reasoning_enabled=False, reasoning_tokens=1024,
               verbose=False) -> LLMResponse:
    # How to pass content beyond text to the LLM:
    # https://community.aws/content/2i4v2vZRb9YgL2RxkawPiF8f0lZ/using-document-chat-with-the-amazon-bedrock-converse-api

    # Payload format:
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/converse.html

    content = []

    if document_content is not None:
        content.append({
            "document": {
                "name": "Document 1",
                "format": document_format.lower(),
                "source": {
                    "bytes": document_content
                }
            }
        })

    content.append(
        {"text": prompt}
    )

    messages = [
        {
            "role": "user",
            "content": content,
        }
    ]

    return __invoke_llm(messages=messages, temperature=temperature, top_k=top_k, top_p=top_p,
                        max_new_tokens=max_new_tokens, model_id=model_id, reasoning_enabled=reasoning_enabled,
                        reasoning_tokens=reasoning_tokens, verbose=verbose)


def extract_items_from_tagged_list(text, tag_name):
    opening_tag = f"<{tag_name}>"
    closing_tag = f"</{tag_name}>"

    regex = fr"{opening_tag}(.*?){closing_tag}"

    items = []
    for match in re.finditer(regex, text, re.DOTALL):
        finding = match.group(1).strip()

        # Find innermost nested opening tag, if any
        # To capture cases like where the model return something like:
        # alkjshdksajhdsakjd <tag> kjsdafkdjhf <tag> dsfkjsdfakjds </tag> dskjfhaksdjhfkdsjf

        innermost_tag_idx = finding.rfind(opening_tag)
        if innermost_tag_idx >= 0:
            finding = finding[innermost_tag_idx + len(opening_tag):].strip()

        if finding:
            items.append(finding)

    return items


def extract_first_item_from_tagged_list(text, tag_name):
    items = extract_items_from_tagged_list(text, tag_name)

    return items[0] if len(items) > 0 else ""


def extract_last_item_from_tagged_list(text, tag_name):
    items = extract_items_from_tagged_list(text, tag_name)

    return items[-1] if len(items) > 0 else ""
