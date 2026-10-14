"""Installation product defaults and ephemeral native Pi provider registration.

Host-specific product settings come only from the optional ``product`` section of
the existing NOETIC_LOCAL_CONFIG JSON. Nothing here bakes an endpoint, model or
credential into the portable tree, and no inference is performed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile

THINKING_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")

_PROVIDER_KEYS = {"name", "base_url", "api", "api_key_provider", "context_window",
                  "max_tokens", "input", "reasoning"}
_NAME_PATTERN = r"[a-z0-9][a-z0-9._-]*"
_MODEL_PATTERN = _NAME_PATTERN + r"/[A-Za-z0-9._-]+"

# Reuses Pi's built-in OpenAI Chat Completions streaming/tool implementation via a
# native provider registration; no adapter or protocol code lives here. The copied-env
# credential reference string is passed through verbatim: native registerProvider
# apiKey resolution already handles literal/$ENV/${ENV}/!command/escaping syntax.
EXTENSION_SOURCE = """\
// Generated Noetic installation provider registration; contains no credential value.
export default async ({ registerProvider }) => {
  const definition = JSON.parse(process.env.NOETIC_MODEL_PROVIDER_DEFINITION);
  const apiKey = process.env.NOETIC_MODEL_PROVIDER_API_KEY_REF;
  if (typeof apiKey !== 'string' || !apiKey) {
    throw new Error('Native provider credential reference is missing');
  }
  registerProvider(definition.name, {
    api: definition.api, baseUrl: definition.baseUrl, apiKey, models: definition.models,
  });
};
"""


def _explicit(value):
    return isinstance(value, str) and value.strip() != ""


def _load_product():
    """Read and validate the optional product section; None means not configured."""
    path = os.environ.get("NOETIC_LOCAL_CONFIG")
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Selected Noetic local configuration is missing or unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Selected Noetic local configuration must be a JSON object")
    product = data.get("product")
    if product is None:
        return None
    return _validate_product(product)


def _validate_product(product):
    if not isinstance(product, dict):
        raise ValueError("Configured product section must be a JSON object")
    client = product.get("client")
    if client != "pi":
        raise ValueError("Configured product client must be Pi; only Pi supports native provider registration")
    model = product.get("model")
    if not isinstance(model, str) or re.fullmatch(_MODEL_PATTERN, model) is None:
        raise ValueError("Configured product model must be an explicit provider/model id")
    thinking = product.get("thinking")
    if thinking not in THINKING_LEVELS:
        raise ValueError("Configured product thinking must be a supported Pi reasoning level")
    provider = product.get("provider")
    if not isinstance(provider, dict) or set(provider) != _PROVIDER_KEYS:
        raise ValueError("Configured product provider requires exactly its schema fields")
    name = provider["name"]
    if not isinstance(name, str) or re.fullmatch(_NAME_PATTERN, name) is None:
        raise ValueError("Configured product provider name is invalid")
    if not model.startswith(name + "/") or len(model) == len(name) + 1:
        raise ValueError("Configured product model must use the configured provider name as its prefix")
    if provider["api"] != "openai-completions":
        raise ValueError("Only the built-in openai-completions adapter is supported for the product provider")
    base_url = provider["base_url"]
    if not isinstance(base_url, str) or not base_url:
        raise ValueError("Configured product provider base_url must be explicit text")
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or "@" in (parsed.netloc or ""):
        raise ValueError("Configured product provider base_url must be a credential-free http(s) URL")
    api_key_provider = provider["api_key_provider"]
    if not isinstance(api_key_provider, str) or not api_key_provider.strip():
        raise ValueError("Configured product provider must reference an existing native credential entry")
    context_window, max_tokens = provider["context_window"], provider["max_tokens"]
    for label, value in (("context_window", context_window), ("max_tokens", max_tokens)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"Configured product provider {label} must be a positive integer")
    if max_tokens >= context_window:
        raise ValueError("Configured product provider max_tokens must be below its context_window")
    input_modes = provider["input"]
    if (not isinstance(input_modes, list) or not input_modes
            or any(mode not in ("text", "image") for mode in input_modes)):
        raise ValueError("Configured product provider input must list text and/or image")
    if provider["reasoning"] is not False:
        raise ValueError("Only a non-reasoning local product model is supported by this registration")
    return {"default": {"client": client, "model": model, "thinking": thinking}, "provider": provider}


def product_configuration():
    """Public configured/default/profile metadata; never includes credential values."""
    product = _load_product()
    if product is None:
        return {"configured": False, "default": None, "profiles": [], "capabilities": {}}
    provider = product["provider"]
    capabilities = {"context_window": provider["context_window"], "max_tokens": provider["max_tokens"],
                    "input": list(provider["input"]), "reasoning": provider["reasoning"]}
    profile = {"id": "installation-default", "client": product["default"]["client"],
               "model": product["default"]["model"], "label": "Installation default",
               "capabilities": dict(capabilities)}
    return {"configured": True, "default": dict(product["default"]),
            "profiles": [profile], "capabilities": capabilities}


def new_options(client=None, model=None, qa_model=None, thinking=None, *, parent=None,
                legacy_client="pi", legacy_model=None, legacy_thinking="high"):
    """Resolve only NEW omitted/None/empty fields; explicit values always win.

    ``parent`` may only provide model/thinking and is never mutated; parent values
    inherit before the installation default. Without a configured product section
    the legacy choices apply unchanged.
    """
    # Validate shapes before any fallback or effect; empty strings stay omitted.
    for label, value in (("client", client), ("model", model),
                         ("qa_model", qa_model), ("thinking", thinking)):
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{label} must be a string or omitted")
    if parent is not None:
        if not isinstance(parent, dict) or set(parent) - {"model", "thinking"}:
            raise ValueError("parent may only provide model and thinking")
        for key in ("model", "thinking"):
            if parent.get(key) is not None and not isinstance(parent[key], str):
                raise ValueError(f"parent {key} must be a string or omitted")
        parent_model, parent_thinking = parent.get("model"), parent.get("thinking")
    else:
        parent_model = parent_thinking = None
    product = _load_product()
    if product is None:
        return {"client": client if _explicit(client) else legacy_client,
                "model": (model if _explicit(model) else
                          parent_model if _explicit(parent_model) else legacy_model),
                "qa_model": qa_model if _explicit(qa_model) else None,
                "thinking": (thinking if _explicit(thinking) else
                             parent_thinking if _explicit(parent_thinking) else legacy_thinking)}
    default = product["default"]
    if _explicit(client) and client != default["client"] and not _explicit(model):
        raise ValueError(f"explicit client {client!r} requires an explicit model; "
                         "the configured product default model cannot apply to it")
    if _explicit(model):
        main = model
    elif _explicit(parent_model):
        main = parent_model
    else:
        main = default["model"]
    return {"client": client if _explicit(client) else default["client"],
            "model": main,
            "qa_model": qa_model if _explicit(qa_model) else main,
            "thinking": (thinking if _explicit(thinking) else
                         parent_thinking if _explicit(parent_thinking) else default["thinking"])}


def _native_key_reference(provider_name):
    """Load the existing native credential CONFIG VALUE; never resolve or print it."""
    agent_dir = os.environ.get("PI_CODING_AGENT_DIR")
    path = Path(agent_dir) / "models.json" if agent_dir else Path.home() / ".pi" / "agent" / "models.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Native provider credential reference is unavailable: {exc}") from exc
    providers = data.get("providers") if isinstance(data, dict) else None
    entry = providers.get(provider_name) if isinstance(providers, dict) else None
    value = entry.get("apiKey") if isinstance(entry, dict) else None
    if not isinstance(value, str) or not value:
        raise ValueError(f"Native provider credential reference is missing for {provider_name!r}")
    return value


def _write_extension(path, source):
    """Write/verify the constant extension cache privately; no secret ever enters it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == source:
            return
    except OSError:
        pass
    # A unique private temporary per caller keeps concurrent cold launches from
    # sharing one deterministic .tmp name; only our own temporary is cleaned up.
    fd, temporary_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(source)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    if path.read_text(encoding="utf-8") != source:
        raise ValueError("Provider extension cache failed verification")


def pi_launch(model, directory, environment):
    """Extra Pi argv and copied environment for the configured product route only.

    For the configured model this registers an ephemeral native provider whose
    factory reuses Pi's built-in openai-completions stream/tool implementation,
    reading the existing native credential reference from a private copied
    environment field. Any other model returns no side effects.
    """
    environment = dict(environment)
    product = _load_product()
    if product is None:
        return [], environment
    default, provider = product["default"], product["provider"]
    if not _explicit(model) or model != default["model"]:
        return [], environment
    # Missing native credential references fail before any cache write.
    reference = _native_key_reference(provider["api_key_provider"])
    if directory is None:
        config_path = os.environ.get("NOETIC_LOCAL_CONFIG")
        if not config_path:
            raise ValueError("Configured product route requires the local configuration path")
        cache = Path(config_path).parent / ".noetic-model-providers"
    else:
        cache = Path(directory)
    extension = cache / "noetic-model-provider.mjs"
    model_id = model[len(provider["name"]) + 1:]
    # Compatibility flags live on each model definition: the installed native
    # streamSimple path reads them from the model, not the provider top level.
    definition = {"name": provider["name"], "api": provider["api"], "baseUrl": provider["base_url"],
                  "models": [{"id": model_id, "name": model, "reasoning": False,
                              "input": list(provider["input"]),
                              "contextWindow": provider["context_window"],
                              "maxTokens": provider["max_tokens"],
                              "compat": {"maxTokensField": "max_tokens", "supportsStore": False,
                                         "supportsDeveloperRole": False, "supportsReasoningEffort": False},
                              "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}}]}
    environment["NOETIC_MODEL_PROVIDER_DEFINITION"] = json.dumps(definition, sort_keys=True)
    environment["NOETIC_MODEL_PROVIDER_API_KEY_REF"] = reference
    _write_extension(extension, EXTENSION_SOURCE)
    return ["--extension", str(extension)], environment
