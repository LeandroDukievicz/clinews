"""Tradução para PT-BR pela API pública do MyMemory.

Não precisa de chave: a API é aberta, e por isso traduzir funciona na primeira
vez que o usuário pressiona `t`, sem configurar nada. Um e-mail opcional, no
parâmetro `de`, sobe a cota diária de 5.000 para 50.000 caracteres por IP.

A API recusa qualquer consulta acima de 500 caracteres, então o texto é
quebrado em pedaços que cabem nesse limite e remontado depois. A cota conta
caracteres, não requisições, então quebrar não custa cota — custa tempo.

`Autodetect` como idioma de origem faz a resposta trazer `detectedLanguage`, e
é isso que permite recusar matéria que já está em português.
"""

from __future__ import annotations

import html
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import __version__
from .themes import config_path

ENDPOINT = "https://api.mymemory.translated.net/get"
MAX_QUERY = 500  # limite por consulta, imposto pela API


class TranslationError(ValueError):
    """Erro amigável ao usuário durante a tradução."""


def load_email() -> str:
    """E-mail opcional que amplia a cota diária. Vazio é um uso válido."""
    if email := os.environ.get("CLINEWS_MYMEMORY_EMAIL", "").strip():
        return email
    try:
        return config_path().with_name("mymemory-email").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_email(email: str) -> None:
    """Guarda o e-mail localmente, legível apenas pelo usuário."""
    target = config_path().with_name("mymemory-email")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(email.strip() + "\n")
    target.chmod(0o600)


def split_for_api(text: str, limit: int = MAX_QUERY) -> list[str]:
    """Quebra `text` em pedaços de até `limit` caracteres.

    Corta primeiro no fim de frase, depois entre palavras, e só parte uma
    palavra quando ela sozinha já passa do limite — um endereço longo colado no
    resumo, por exemplo. Pedaço nenhum sai vazio.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    pedacos: list[str] = []
    atual = ""
    for frase in re.split(r"(?<=[.!?…])\s+", text):
        while len(frase) > limit:
            corte = frase.rfind(" ", 0, limit + 1)
            corte = corte if corte > 0 else limit
            if atual:
                pedacos.append(atual)
                atual = ""
            pedacos.append(frase[:corte].strip())
            frase = frase[corte:].strip()
        if not frase:
            continue
        candidato = f"{atual} {frase}".strip()
        if len(candidato) <= limit:
            atual = candidato
        else:
            if atual:
                pedacos.append(atual)
            atual = frase
    if atual:
        pedacos.append(atual)
    return [p for p in pedacos if p]


def _translate_chunk(text: str, email: str) -> tuple[str, str]:
    """Traduz um pedaço e devolve (tradução, idioma detectado em maiúsculas)."""
    parametros = {"q": text, "langpair": "Autodetect|pt-BR"}
    if email:
        parametros["de"] = email
    request = Request(
        f"{ENDPOINT}?{urlencode(parametros)}",
        headers={"User-Agent": f"clinews/{__version__}"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            resultado = json.loads(response.read(1_000_001))
    except HTTPError as exc:
        raise TranslationError(f"O MyMemory respondeu {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise TranslationError(f"Não foi possível conectar à API de tradução: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TranslationError("A API de tradução retornou uma resposta inválida.") from exc

    if not isinstance(resultado, dict):
        raise TranslationError("A API de tradução retornou uma resposta inválida.")
    dados = resultado.get("responseData")
    if not isinstance(dados, dict):
        raise TranslationError("A API de tradução retornou uma resposta inválida.")

    status = str(resultado.get("responseStatus", "")).strip()
    if status not in ("200", ""):
        detalhe = str(resultado.get("responseDetails") or "").strip()
        # A cota estourada é o erro que o usuário mais vai encontrar, e a saída
        # dele é o e-mail — vale dizer isso em vez de repassar o texto cru.
        if "ALL AVAILABLE FREE TRANSLATIONS" in detalhe.upper() or resultado.get("quotaFinished"):
            raise TranslationError(
                "A cota diária de tradução acabou. Defina CLINEWS_MYMEMORY_EMAIL "
                "com um e-mail válido para ampliá-la, ou tente amanhã."
            )
        raise TranslationError(f"O MyMemory recusou a tradução: {detalhe or status}")

    traduzido = html.unescape(str(dados.get("translatedText") or "")).strip()
    if not traduzido:
        raise TranslationError("A API retornou uma tradução vazia.")
    return traduzido, str(dados.get("detectedLanguage") or "").upper()


def translate_to_portuguese(title: str, summary: str, email: str = "") -> tuple[str, str, str]:
    """Traduz título e resumo para PT-BR e devolve também o idioma de origem.

    O pedaço mais longo vai primeiro, de propósito: a detecção erra com
    facilidade num título de seis palavras, e descobrir ali que a matéria já
    está em português evita gastar cota com o resto.
    """
    email = email.strip() or load_email()
    titulo = title.strip()
    if not titulo:
        raise TranslationError("A matéria não tem título para traduzir.")

    linhas = summary.splitlines() if summary.strip() else []
    # Cada pedaço carrega a linha de onde veio, para remontar o resumo com os
    # mesmos parágrafos que o feed mandou.
    pedacos: list[tuple[int, str]] = [(-1, titulo)]
    for indice, linha in enumerate(linhas):
        pedacos.extend((indice, parte) for parte in split_for_api(linha))

    mais_longo = max(range(len(pedacos)), key=lambda i: len(pedacos[i][1]))
    traduzido, detectado = _translate_chunk(pedacos[mais_longo][1], email)
    if detectado.startswith("PT"):
        raise TranslationError("Esta matéria já está em português.")

    traducoes = {mais_longo: traduzido}
    for indice, (_, texto) in enumerate(pedacos):
        if indice != mais_longo:
            traducoes[indice] = _translate_chunk(texto, email)[0]

    partes_por_linha: dict[int, list[str]] = {}
    for indice, (linha, _) in enumerate(pedacos):
        if linha >= 0:
            partes_por_linha.setdefault(linha, []).append(traducoes[indice])
    resumo = "\n".join(
        " ".join(partes_por_linha[i]) if i in partes_por_linha else ""
        for i in range(len(linhas))
    ) if linhas else ""
    return traducoes[0], resumo, detectado
