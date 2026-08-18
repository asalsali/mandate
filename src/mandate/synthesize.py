"""LLM bridge for synthesize blocks."""

from __future__ import annotations

import json
import os
from typing import Any

from .ast_nodes import ArrayType, PrimitiveType, RecordType


def build_prompt(instruction: str, given_data: dict[str, Any], produce_type: Any) -> str:
    """Build an LLM prompt from synthesize block parameters."""
    type_hint = _type_to_hint(produce_type)

    parts = [
        f"INSTRUCTION: {instruction}",
        "",
        "GIVEN DATA:",
    ]
    for key, value in given_data.items():
        parts.append(f"  {key}: {json.dumps(value) if not isinstance(value, str) else value}")

    parts.extend([
        "",
        f"REQUIRED OUTPUT TYPE: {type_hint}",
        "",
        "Respond with ONLY the output value. No explanation, no markdown.",
    ])

    if isinstance(produce_type, RecordType):
        parts.append("Respond with valid JSON matching the required type.")
    elif isinstance(produce_type, ArrayType):
        parts.append("Respond with a valid JSON array.")

    return "\n".join(parts)


def _type_to_hint(t: Any) -> str:
    """Convert a type node to a human-readable hint."""
    if isinstance(t, PrimitiveType):
        return t.name
    if isinstance(t, ArrayType):
        return f"array of {_type_to_hint(t.element_type)}"
    if isinstance(t, RecordType):
        fields = ", ".join(f"{k}: {_type_to_hint(v)}" for k, v in t.fields.items())
        return f"object with fields {{ {fields} }}"
    return str(t)


def parse_response(raw: str, produce_type: Any) -> Any:
    """Parse LLM response into the expected type."""
    raw = raw.strip()

    if isinstance(produce_type, PrimitiveType):
        if produce_type.name == "string":
            return raw
        if produce_type.name == "int":
            return int(raw)
        if produce_type.name == "float":
            return float(raw)
        if produce_type.name == "bool":
            return raw.lower() in ("true", "yes", "1")

    if isinstance(produce_type, (RecordType, ArrayType)):
        return json.loads(raw)

    return raw


def synthesize_call(
    given: dict[str, Any],
    produce_type: Any,
    instruction: str,
    model: str = "gpt-4o-mini",
) -> Any:
    """Execute a synthesize block by calling an LLM.

    Uses the OpenAI API. Set OPENAI_API_KEY in your environment.
    Falls back to a stub response if no API key is available.
    """
    prompt = build_prompt(instruction, given, produce_type)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # Stub mode -- return a plausible default for testing
        return _stub_response(produce_type, given, instruction)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a precise data generator. Follow the instruction exactly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content or ""
        return parse_response(raw, produce_type)
    except ImportError:
        return _stub_response(produce_type, given, instruction)
    except Exception as e:
        raise RuntimeError(f"Synthesize call failed: {e}") from e


def _stub_response(produce_type: Any, given: dict, instruction: str) -> Any:
    """Generate a plausible stub response when no LLM is available."""
    if isinstance(produce_type, PrimitiveType):
        if produce_type.name == "string":
            # Try to produce something contextual
            name = given.get("name", "World")
            return f"Hello, {name}! (stub response)"
        if produce_type.name == "int":
            return 42
        if produce_type.name == "float":
            return 0.85
        if produce_type.name == "bool":
            return True

    if isinstance(produce_type, ArrayType):
        return []

    if isinstance(produce_type, RecordType):
        result = {}
        for fname, ftype in produce_type.fields.items():
            result[fname] = _stub_response(ftype, given, instruction)
        return result

    return "(stub)"
