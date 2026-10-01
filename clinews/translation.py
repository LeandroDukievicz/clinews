"""Integração opcional com a API DeepL para traduzir resumos de notícias."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .themes import config_path


class TranslationError(ValueError):
    """Erro amigável ao usuário durante a tradução."""


def load_api_key() -> str:
    """Lê a chave do ambiente ou do arquivo privado de configuração do usuário."""
    if key := os.environ.get("CLINEWS_DEEPL_API_KEY", "").strip():
        return key
    try:
        return config_path().with_name("deepl-api-key").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_api_key(api_key: str) -> None:
    """Salva a chave localmente com permissão de leitura apenas para o usuário."""
    target = config_path().with_name("deepl-api-key")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
        secret_file.write(api_key.strip() + "\n")
    target.chmod(0o600)


def translate_to_portuguese(title: str, summary: str) -> tuple[str, str, str]:
    """Traduz título e resumo para PT-BR e retorna também o idioma detectado."""
    api_key = load_api_key()
    if not api_key:
        raise TranslationError(
            "Configure CLINEWS_DEEPL_API_KEY com sua chave da DeepL API."
        )

    texts = [title, summary] if summary.strip() else [title]
    endpoint = os.environ.get(
        "CLINEWS_DEEPL_API_URL", "https://api-free.deepl.com/v2/translate"
    ).rstrip("/")
    body = json.dumps({"text": texts, "target_lang": "PT-BR"}).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"DeepL-Auth-Key {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "clinews/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            result = json.loads(response.read(1_000_001))
    except HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("message", detail)
        except (json.JSONDecodeError, AttributeError):
            pass
        raise TranslationError(f"DeepL respondeu {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TranslationError(f"Não foi possível conectar à DeepL API: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TranslationError("A DeepL API retornou uma resposta inválida.") from exc

    translations = result.get("translations", [])
    if len(translations) != len(texts):
        raise TranslationError("A DeepL API não retornou todos os textos traduzidos.")
    detected = (translations[-1].get("detected_source_language") or "").upper()
    if detected != "EN":
        raise TranslationError("Esta matéria não parece estar em inglês.")
    translated_title = translations[0].get("text", "")
    translated_summary = translations[1].get("text", "") if summary.strip() else ""
    if not translated_title or (summary.strip() and not translated_summary):
        raise TranslationError("A DeepL API retornou uma tradução vazia.")
    return translated_title, translated_summary, detected
