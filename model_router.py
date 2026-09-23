"""Provider-agnostic text model router for JakeAI.

This module deliberately keeps provider activation explicit and fail-closed.
The default remains OpenAI so existing JakeAI Direct behavior does not change
unless DIRECT_MODEL_PROVIDER is set to another supported provider and that
provider's server-side credential is present.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

SUPPORTED_PROVIDERS = {"openai", "mimo"}
DEFAULT_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_MIMO_MODEL = "mimo-v2.6-flash"
DEFAULT_MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"


class ModelRouterError(RuntimeError):
    """Raised for provider configuration or transport failures."""


def selected_provider() -> str:
    provider = os.environ.get("DIRECT_MODEL_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ModelRouterError(f"Unsupported model provider: {provider or '<empty>'}")
    return provider


def selected_model(provider: Optional[str] = None) -> str:
    provider = provider or selected_provider()
    if provider == "openai":
        return os.environ.get("DIRECT_OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
    if provider == "mimo":
        return os.environ.get("DIRECT_MIMO_MODEL", DEFAULT_MIMO_MODEL).strip() or DEFAULT_MIMO_MODEL
    raise ModelRouterError(f"Unsupported model provider: {provider}")


def _api_key(provider: str) -> str:
    if provider == "openai":
        return os.environ.get("OPENAI_API_KEY", "").strip()
    if provider == "mimo":
        return os.environ.get("MIMO_API_KEY", "").strip()
    return ""


def _base_url(provider: str) -> str:
    if provider == "openai":
        return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    if provider == "mimo":
        return os.environ.get("MIMO_BASE_URL", DEFAULT_MIMO_BASE_URL).strip().rstrip("/")
    raise ModelRouterError(f"Unsupported model provider: {provider}")


def execution_configured(provider: Optional[str] = None) -> bool:
    try:
        provider = provider or selected_provider()
    except ModelRouterError:
        return False
    return provider in SUPPORTED_PROVIDERS and bool(_api_key(provider))


def extract_response_text(data: Dict[str, Any]) -> str:
    top = data.get("output_text")
    if isinstance(top, str) and top.strip():
        return top.strip()

    parts = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(str(content["text"]))
    return "\n".join(parts).strip()


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int = 45) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ModelRouterError(f"Provider rejected request with HTTP {exc.code}") from exc
    except Exception as exc:
        raise ModelRouterError("Provider request failed") from exc


def run_text(
    prompt: str,
    instructions: str,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_output_tokens: int = 1400,
    reasoning_effort: str = "low",
) -> Dict[str, Any]:
    provider = provider or selected_provider()
    if provider not in SUPPORTED_PROVIDERS:
        raise ModelRouterError(f"Unsupported model provider: {provider}")

    key = _api_key(provider)
    if not key:
        raise ModelRouterError(f"{provider} credential is not configured")

    model = model or selected_model(provider)
    base_url = _base_url(provider)
    url = base_url + "/responses"

    if provider == "openai":
        payload: Dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": prompt,
            "max_output_tokens": int(max_output_tokens),
            "reasoning": {"effort": reasoning_effort},
            "store": False,
            "metadata": {"product": "jakeai_direct"},
        }
    else:
        # Keep the MiMo request intentionally minimal. Xiaomi documents an
        # OpenAI-compatible Responses endpoint. Tool execution is not enabled
        # here while MiMo V2.6 tool-call regressions are under evaluation.
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
            "max_output_tokens": int(max_output_tokens),
            "stream": False,
        }

    data = _post_json(
        url,
        payload,
        {"Authorization": "Bearer " + key, "User-Agent": "JakeAI-Model-Router/1.0"},
    )
    text = extract_response_text(data)
    if not text:
        raise ModelRouterError("Provider returned no usable model output")

    usage = data.get("usage") or {}
    return {
        "text": text,
        "provider": provider,
        "model": str(data.get("model") or model),
        "response_id": str(data.get("id") or ""),
        "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
    }
