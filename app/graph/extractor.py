# """
# Uses an LLM (via OpenRouter) to pull structured facts/opinions/events/
# relationships out of a single text chunk, per the schema in `schema.py`.
#
# Requires OPENROUTER_API_KEY in the environment.
# """
#
# import json
#
# from app.graph.schema import EXTRACTION_SCHEMA_DESCRIPTION
# from app.llm.openrouter_client import chat_completion
#
# _SYSTEM_PROMPT = (
#     "You extract structured information from a piece of text about a person "
#     "(the persona), for a knowledge graph. Be precise and conservative: only "
#     "extract what is explicitly stated. " + EXTRACTION_SCHEMA_DESCRIPTION
# )
#
# _EMPTY_RESULT = {"facts": [], "opinions": [], "events": [], "relationships": []}
#
#
# def _parse_response(raw_text: str) -> dict:
#     """Parse the model's JSON response, tolerating stray markdown fences
#     and, defensively, any leading/trailing prose a model might emit
#     around the JSON (e.g. a reasoning model that didn't fully respect
#     `reasoning.exclude`)."""
#     cleaned = raw_text.strip()
#     if cleaned.startswith("```"):
#         cleaned = cleaned.strip("`")
#         if cleaned.startswith("json"):
#             cleaned = cleaned[4:]
#         cleaned = cleaned.strip()
#
#     try:
#         data = json.loads(cleaned)
#     except json.JSONDecodeError:
#         # Fallback: extract the outermost {...} block, in case the model
#         # wrapped the JSON in prose/reasoning despite instructions.
#         start = cleaned.find("{")
#         end = cleaned.rfind("}")
#         if start == -1 or end == -1 or end <= start:
#             raise ValueError(
#                 f"Model did not return valid JSON and no JSON object could be "
#                 f"found. Raw response: {raw_text!r}"
#             )
#         try:
#             data = json.loads(cleaned[start : end + 1])
#         except json.JSONDecodeError as e:
#             raise ValueError(f"Model did not return valid JSON: {e}\nRaw response: {raw_text!r}")
#
#         result = dict(_EMPTY_RESULT)
#         for key in result:
#             value = data.get(key, [])
#             if not isinstance(value, list):
#                 raise ValueError(f"Expected a list for '{key}', got {type(value).__name__}")
#             # Some models (especially smaller/free ones) occasionally return a
#             # plain string instead of the expected {"text": ...} object for a
#             # list item. Normalize rather than crash the whole extraction run.
#             result[key] = [_normalize_item(item) for item in value]
#         return result
#
# def _normalize_item(item) -> dict:
#     if isinstance(item, str):
#         return {"text": item}
#     if isinstance(item, dict):
#         return item
#     return {"text": str(item)}
#
#
# def extract_from_chunk(chunk_text: str, model: str | None = None) -> dict:
#     """
#     Extract facts/opinions/events/relationships from a single chunk of text.
#
#     Returns a dict: {"facts": [...], "opinions": [...], "events": [...], "relationships": [...]}
#     Any category with nothing found comes back as an empty list.
#     """
#     if not chunk_text.strip():
#         return dict(_EMPTY_RESULT)
#
#     messages = [
#         {"role": "system", "content": _SYSTEM_PROMPT},
#         {"role": "user", "content": chunk_text},
#     ]
#     # exclude_reasoning strips chain-of-thought for models that expose one
#     # (e.g. "thinking" models); max_tokens raised to give room for both
#     # reasoning (if not fully excludable) and the JSON payload itself.
#     raw_text = chat_completion(messages, model=model, max_tokens=4000, exclude_reasoning=True)
#     return _parse_response(raw_text)

"""
Uses an LLM (via OpenRouter) to pull structured facts/opinions/events/
relationships out of a single text chunk, per the schema in `schema.py`.

Requires OPENROUTER_API_KEY in the environment.
"""

import json
import re
from app.graph.schema import PersonaExtraction, EXTRACTION_SCHEMA_DESCRIPTION
from app.llm.openrouter_client import chat_completion

_SYSTEM_PROMPT = (
    "You extract structured information from a piece of text about a person "
    "(the persona), for a knowledge graph. Be precise and conservative: only "
    "extract what is explicitly stated. " + EXTRACTION_SCHEMA_DESCRIPTION
)

_EMPTY_RESULT = {"facts": [], "opinions": [], "events": [], "relationships": []}


def _normalize_item(item) -> dict:
    """Some models occasionally return a plain string instead of the
    expected {"text": ...} object for a list item. Normalize rather
    than crash the whole extraction run."""
    if isinstance(item, str):
        return {"text": item}
    if isinstance(item, dict):
        return item
    return {"text": str(item)}


def _parse_response(raw_text) -> dict:
    """Parse the model's JSON response, tolerating stray markdown fences
    and, defensively, any leading/trailing prose a model might emit
    around the JSON (e.g. a reasoning model that didn't fully respect
    `reasoning.exclude`)."""
    if not raw_text or not isinstance(raw_text, str):
        raise ValueError(f"Model returned no usable text content: {raw_text!r}")

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: extract the outermost {...} block, in case the model
        # wrapped the JSON in prose/reasoning despite instructions.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(
                f"Model did not return valid JSON and no JSON object could be "
                f"found. Raw response: {raw_text!r}"
            )
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as e:
            raise ValueError(f"Model did not return valid JSON: {e}\nRaw response: {raw_text!r}")

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object at the top level, got {type(data).__name__}")

    result = dict(_EMPTY_RESULT)
    for key in result:
        value = data.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"Expected a list for '{key}', got {type(value).__name__}")
        result[key] = [_normalize_item(item) for item in value]
    return result


def extract_from_chunk(text: str) -> PersonaExtraction:
    system_prompt = f"""{EXTRACTION_SCHEMA_DESCRIPTION}

    CRITICAL INSTRUCTION: You MUST output ONLY raw, valid JSON.
    Do not include markdown formatting (like ```json), explanations, conversational text, or Turtle/RDF code.
    Extract as much relevant information as you can find, even if the text is messy or from a scraped website.
    If a specific field (like personality_traits) is not present, just return an empty list [] for that field.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]

    raw_response = chat_completion(messages, exclude_reasoning=True, max_tokens=4000)

    cleaned_response = raw_response.strip()
    markdown_match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned_response, re.DOTALL)
    if markdown_match:
        cleaned_response = markdown_match.group(1).strip()

    try:
        parsed_data = json.loads(cleaned_response)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nRaw output from model:\n{raw_response}")

    try:
        return PersonaExtraction(**parsed_data)
    except Exception as e:
        # Pydantic validation errors (wrong field names, wrong types, etc.)
        # were previously uncaught here — they'd propagate as a generic
        # exception with no context about what the model actually returned,
        # making failures very hard to diagnose. Wrap with the raw JSON visible.
        raise ValueError(f"Model JSON didn't match expected schema: {e}\nParsed JSON was:\n{parsed_data}")