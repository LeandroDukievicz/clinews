"""Integração opcional com a API Google Cloud Translation v2."""

from __future__ import annotations

import json
import html
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .themes import config_path


class TranslationError(ValueError):
    """Erro amigável ao usuário durante a tradução."""


def load_api_key() -> str:
    """Lê a chave do ambiente ou do arquivo privado de configuração."""
    if key := os.environ.get("CLINEWS_GOOGLE_TRANSLATE_API_KEY", "").strip():
        return key
    try:
        return config_path().with_name("google-translate-api-key").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_api_key(api_key: str) -> None:
    """Salva a chave localmente com permissão de leitura apenas para o usuário."""
    target = config_path().with_name("google-translate-api-key")
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
            "Configure CLINEWS_GOOGLE_TRANSLATE_API_KEY com sua chave do Google Cloud."
        )

    texts = [title, summary] if summary.strip() else [title]
    endpoint = os.environ.get(
        "CLINEWS_GOOGLE_TRANSLATE_API_URL",
        "https://translation.googleapis.com/language/translate/v2",
    ).rstrip("/")
    body = urlencode([("q", text) for text in texts] + [
        ("target", "pt-BR"), ("format", "text"), ("key", api_key)
    ]).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "clinews/0.2"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read(1_000_001))
    except HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("error", {}).get("message", detail)
        except (json.JSONDecodeError, AttributeError):
            pass
        raise TranslationError(f"Google Cloud Translation respondeu {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TranslationError(f"Não foi possível conectar à API de tradução: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TranslationError("A API de tradução retornou uma resposta inválida.") from exc

    translations = result.get("data", {}).get("translations", [])
    if len(translations) != len(texts):
        raise TranslationError("A API não retornou todos os textos traduzidos.")
    detected = (translations[0].get("detectedSourceLanguage") or "").upper()
    if detected != "EN":
        raise TranslationError("Esta matéria não parece estar em inglês.")
    translated_title = html.unescape(translations[0].get("translatedText", ""))
    translated_summary = html.unescape(translations[1].get("translatedText", "")) if summary.strip() else ""
    if not translated_title or (summary.strip() and not translated_summary):
        raise TranslationError("A API retornou uma tradução vazia.")
    return translated_title, translated_summary, detected
