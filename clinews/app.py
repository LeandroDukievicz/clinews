"""Prévia funcional de um leitor RSS em modo texto."""

from __future__ import annotations

import argparse
import curses
import html
import os
import sqlite3
import textwrap
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from .themes import THEMES, basic_color, load_theme, nearest_xterm, save_theme
from .suggestions import SUGGESTIONS, Suggestion
from .translation import TranslationError, load_api_key, save_api_key, translate_to_portuguese

USER_AGENT = "clinews/0.2.1 (+terminal RSS reader)"
ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.feeds: list[str] = []
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "link" and "alternate" in (attrs_dict.get("rel") or "").lower().split():
            if (attrs_dict.get("type") or "").lower() in ("application/rss+xml", "application/atom+xml"):
                if attrs_dict.get("href"):
                    self.feeds.append(attrs_dict["href"])
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "li"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def plain_text(markup: str) -> str:
    parser = PageParser()
    parser.feed(markup)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line).strip()


def checked_url(url: str) -> str:
    url = url.strip()
    if not urlparse(url).scheme:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Use um endereço HTTP ou HTTPS válido.")
    return url


def get_url(url: str) -> tuple[str, bytes, str]:
    request = Request(checked_url(url), headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=12) as response:
        data = response.read(5_000_001)
        if len(data) > 5_000_000:
            raise ValueError("Resposta grande demais (limite: 5 MB).")
        charset = response.headers.get_content_charset() or "utf-8"
        return response.url, data, charset


def tag_text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    return "".join(child.itertext()).strip() if child is not None else ""


def normalized_date(value: str) -> str:
    if not value:
        return ""
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError, IndexError):
            return value[:10]
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")


def parse_feed(data: bytes, base_url: str) -> tuple[str, list[dict[str, str]]]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("O endereço não contém um RSS/Atom válido.") from exc
    articles: list[dict[str, str]] = []
    if root.tag in ("rss", "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF"):
        channel = root.find("channel")
        if channel is None:
            channel = root
        title = tag_text(channel, "title") or urlparse(base_url).hostname or "Feed"
        for item in channel.findall("item"):
            link = urljoin(base_url, tag_text(item, "link"))
            guid = tag_text(item, "guid") or link or tag_text(item, "title")
            articles.append({"guid": guid, "title": tag_text(item, "title") or "Sem título",
                             "url": link, "summary": plain_text(tag_text(item, CONTENT + "encoded") or tag_text(item, "description")),
                             "published": normalized_date(tag_text(item, "pubDate"))})
    elif root.tag == ATOM + "feed":
        title = tag_text(root, ATOM + "title") or urlparse(base_url).hostname or "Feed"
        for entry in root.findall(ATOM + "entry"):
            links = entry.findall(ATOM + "link")
            link = next((x.get("href", "") for x in links if x.get("rel", "alternate") == "alternate"), "")
            link = urljoin(base_url, link) if link else ""
            guid = tag_text(entry, ATOM + "id") or link or tag_text(entry, ATOM + "title")
            articles.append({"guid": guid, "title": tag_text(entry, ATOM + "title") or "Sem título",
                             "url": link, "summary": plain_text(tag_text(entry, ATOM + "content") or tag_text(entry, ATOM + "summary")),
                             "published": normalized_date(tag_text(entry, ATOM + "published") or tag_text(entry, ATOM + "updated"))})
    else:
        raise ValueError("Formato de feed não reconhecido (use RSS ou Atom).")
    return html.unescape(title), articles


def discover_feed(site_url: str) -> tuple[str, str, list[dict[str, str]]]:
    final_url, data, charset = get_url(site_url)
    try:
        title, articles = parse_feed(data, final_url)
        return final_url, title, articles
    except ValueError:
        pass
    parser = PageParser()
    parser.feed(data.decode(charset, errors="replace"))
    base = final_url
    candidates = [urljoin(base, href) for href in parser.feeds]
    candidates += [urljoin(base, path) for path in ("/feed", "/feed.xml", "/rss.xml", "/atom.xml")]
    for candidate in dict.fromkeys(candidates):
        try:
            feed_url, feed_data, _ = get_url(candidate)
            title, articles = parse_feed(feed_data, feed_url)
            return feed_url, title, articles
        except (ValueError, HTTPError, URLError, TimeoutError, OSError):
            continue
    raise ValueError("Não encontrei RSS/Atom nesse site. Cole o link direto do feed.")


def data_path() -> Path:
    if snap_data := os.environ.get("SNAP_USER_COMMON"):
        return Path(snap_data) / "data" / "clinews.db"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "clinews" / "clinews.db"


def open_db(path: Path | str = ":memory:") -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys = ON")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY, site_url TEXT NOT NULL, feed_url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY, feed_id INTEGER NOT NULL REFERENCES feeds(id),
            guid TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
            summary TEXT NOT NULL, published TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0,
            UNIQUE(feed_id, guid)
        );
        CREATE TABLE IF NOT EXISTS translations (
            article_id INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
            title TEXT NOT NULL, summary TEXT NOT NULL, source_language TEXT NOT NULL,
            target_language TEXT NOT NULL DEFAULT 'PT-BR'
        );
    """)
    return db


def store_articles(db: sqlite3.Connection, feed_id: int, articles: list[dict[str, str]]) -> int:
    before = db.total_changes
    for article in articles:
        if article["guid"]:
            db.execute("""INSERT OR IGNORE INTO articles
                (feed_id, guid, title, url, summary, published) VALUES (?, ?, ?, ?, ?, ?)""",
                (feed_id, article["guid"], article["title"], article["url"], article["summary"], article["published"]))
    db.commit()
    return db.total_changes - before


def add_site(db: sqlite3.Connection, url: str, display_title: str | None = None) -> tuple[str, int]:
    url = checked_url(url)
    feed_url, title, articles = discover_feed(url)
    title = display_title or title
    db.execute("INSERT OR IGNORE INTO feeds (site_url, feed_url, title) VALUES (?, ?, ?)", (url, feed_url, title))
    db.commit()
    feed_id = db.execute("SELECT id FROM feeds WHERE feed_url = ?", (feed_url,)).fetchone()["id"]
    return title, store_articles(db, feed_id, articles)


def refresh(db: sqlite3.Connection) -> tuple[int, list[str]]:
    added = 0
    errors = []
    for feed in db.execute("SELECT * FROM feeds ORDER BY id").fetchall():
        try:
            final_url, data, _ = get_url(feed["feed_url"])
            _, articles = parse_feed(data, final_url)
            db.execute("UPDATE feeds SET feed_url = ? WHERE id = ?", (final_url, feed["id"]))
            added += store_articles(db, feed["id"], articles)
        except (ValueError, HTTPError, URLError, TimeoutError, OSError, sqlite3.IntegrityError) as exc:
            errors.append(f"{feed['title']}: {exc}")
    db.commit()
    return added, errors


def demo_db() -> sqlite3.Connection:
    db = open_db()
    samples = [
        ("Tecnologia", [
            ("Uma nova forma de acompanhar a web", "Um leitor simples organiza as atualizações dos sites que você escolheu."),
            ("Por que o RSS ainda é útil", "RSS permite receber novidades sem depender de algoritmos ou contas."),
        ]),
        ("Ciência", [
            ("Pesquisadores publicam novos resultados", "Um resumo da pesquisa aparece aqui. Pressione Enter para ler no terminal."),
            ("O céu desta semana", "Notícias recentes do seu site de astronomia favorito."),
        ]),
        ("Cultura", [
            ("Livros para descobrir neste mês", "Você decide quais sites entram na sua lista de leitura."),
        ]),
    ]
    for index, (title, items) in enumerate(samples, 1):
        cur = db.execute("INSERT INTO feeds (site_url, feed_url, title) VALUES (?, ?, ?)",
                         (f"https://exemplo{index}.org", f"https://exemplo{index}.org/feed", title))
        store_articles(db, cur.lastrowid, [
            {"guid": f"demo-{index}-{n}", "title": headline, "url": "", "summary": summary,
             "published": f"2026-10-{1+n:02d} 09:00"} for n, (headline, summary) in enumerate(items)
        ])
    return db


def draw(stdscr: curses.window, y: int, x: int, text: str, width: int, attr: int = 0) -> None:
    if width < 1:
        return
    try:
        stdscr.addnstr(y, x, text.ljust(width), width, attr)
    except curses.error:
        pass


def apply_theme(stdscr: curses.window, name: str) -> dict[str, int]:
    roles = {
        "body": ("fg", "bg"), "header": ("fg", "surface"),
        "heading": ("accent", "bg"), "accent": ("accent", "bg"),
        "muted": ("muted", "bg"), "selected": ("selected_fg", "selection"),
        "unread": ("unread", "bg"), "status": ("muted", "bg"),
        "footer": ("fg", "surface"), "link": ("link", "bg"),
    }
    styles = {role: 0 for role in roles}
    if not curses.has_colors():
        styles["header"] = styles["footer"] = styles["selected"] = curses.A_REVERSE
        return styles
    curses.start_color()
    convert = nearest_xterm if curses.COLORS >= 256 else basic_color
    palette = THEMES[name]
    for index, (role, (foreground, background)) in enumerate(roles.items(), 1):
        curses.init_pair(index, convert(palette[foreground]), convert(palette[background]))
        styles[role] = curses.color_pair(index)
    stdscr.bkgd(" ", styles["body"])
    return styles


def prompt(stdscr: curses.window, label: str, styles: dict[str, int]) -> str:
    height, width = stdscr.getmaxyx()
    label = label[:max(1, width - 2)]
    curses.echo()
    curses.curs_set(1)
    draw(stdscr, height - 1, 0, label, width, styles["footer"])
    stdscr.refresh()
    try:
        value = stdscr.getstr(height - 1, min(len(label), width - 1), max(1, width - len(label) - 1))
        return value.decode("utf-8", errors="replace").strip()
    finally:
        curses.noecho()
        curses.curs_set(0)


def prompt_secret(stdscr: curses.window, label: str, styles: dict[str, int]) -> str:
    height, width = stdscr.getmaxyx()
    label = label[:max(1, width - 2)]
    curses.noecho()
    curses.curs_set(1)
    draw(stdscr, height - 1, 0, label, width, styles["footer"])
    stdscr.refresh()
    try:
        value = stdscr.getstr(height - 1, min(len(label), width - 1), max(1, width - len(label) - 1))
        return value.decode("utf-8", errors="replace").strip()
    finally:
        curses.curs_set(0)


def reader(stdscr: curses.window, db: sqlite3.Connection, article: sqlite3.Row,
           styles: dict[str, int]) -> None:
    offset = 0
    cached = db.execute("SELECT * FROM translations WHERE article_id=?", (article["id"],)).fetchone()
    showing_translation = False
    status = ""
    while True:
        height, width = stdscr.getmaxyx()
        title = cached["title"] if showing_translation and cached else article["title"]
        summary = cached["summary"] if showing_translation and cached else article["summary"]
        lines = [title, "", article["published"], ""]
        for paragraph in summary.splitlines() or ["Sem resumo no feed. Abra o link para ler o texto completo."]:
            lines.extend(textwrap.wrap(paragraph, width=max(20, width - 4)) or [""])
        lines.extend(["", "Link da matéria original:"])
        lines.extend(textwrap.wrap(article["url"], width=max(20, width - 4),
                                   break_long_words=True, break_on_hyphens=False)
                     if article["url"] else ["Não informado pelo feed."])
        stdscr.erase()
        heading = " clinews  /  leitura · tradução PT-BR" if showing_translation else " clinews  /  leitura"
        draw(stdscr, 0, 0, heading, width, styles["header"] | curses.A_BOLD)
        for row, line in enumerate(lines[offset:offset + height - 3], 1):
            color = styles["heading"] if row == 1 and offset == 0 else styles["body"]
            if line == "Link da matéria original:" or line.startswith("http://") or line.startswith("https://"):
                color = styles["link"]
            draw(stdscr, row, 2, line, max(1, width - 4), color | (curses.A_BOLD if row == 1 and offset == 0 else 0))
        draw(stdscr, height - 2, 0, status, width, styles["status"])
        draw(stdscr, height - 1, 0, " j/k rolar   t traduzir/voltar   o abrir link   q voltar", width, styles["footer"])
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), 27, 10):
            return
        if key in (ord("j"), curses.KEY_DOWN):
            offset = min(max(0, len(lines) - height + 3), offset + 1)
        elif key in (ord("k"), curses.KEY_UP):
            offset = max(0, offset - 1)
        elif key == ord("o") and article["url"]:
            import webbrowser
            webbrowser.open(article["url"])
        elif key == ord("t"):
            if showing_translation:
                showing_translation = False
                status = "Texto original."
            else:
                if not cached:
                    api_key = load_api_key()
                    if not api_key:
                        api_key = prompt_secret(stdscr, " Chave DeepL API (entrada oculta; Enter cancela): ", styles)
                        if not api_key:
                            status = "Tradução cancelada."
                            continue
                        try:
                            save_api_key(api_key)
                        except OSError as exc:
                            status = f"Não foi possível salvar a chave localmente: {exc}"
                            continue
                    status = "Traduzindo título e resumo do feed..."
                    draw(stdscr, height - 2, 0, status, width, styles["status"])
                    stdscr.refresh()
                    try:
                        translated_title, translated_summary, source_language = translate_to_portuguese(
                            article["title"], article["summary"]
                        )
                        db.execute("""INSERT OR REPLACE INTO translations
                            (article_id, title, summary, source_language, target_language)
                            VALUES (?, ?, ?, ?, 'PT-BR')""",
                                   (article["id"], translated_title, translated_summary, source_language))
                        db.commit()
                        cached = db.execute("SELECT * FROM translations WHERE article_id=?",
                                            (article["id"],)).fetchone()
                    except TranslationError as exc:
                        status = str(exc)
                        continue
                showing_translation = True
                status = "Tradução salva localmente. Pressione t para ver o original."
            offset = 0


def choose_theme(stdscr: curses.window, current: str) -> str:
    names = list(THEMES)
    selected = names.index(current)
    while True:
        styles = apply_theme(stdscr, names[selected])
        height, width = stdscr.getmaxyx()
        stdscr.erase()
        draw(stdscr, 0, 0, " CLINEWS  /  temas", width, styles["header"] | curses.A_BOLD)
        draw(stdscr, 1, 2, "Escolha um tema (prévia ao mover):", width - 4, styles["heading"])
        visible = max(1, height - 4)
        start = max(0, selected - visible + 1)
        for row, name in enumerate(names[start:start + visible], 2):
            attr = styles["selected"] if start + row - 2 == selected else styles["body"]
            draw(stdscr, row, 2, f" {name}", width - 4, attr)
        draw(stdscr, height - 1, 0, " j/k escolher   Enter salvar   Esc cancelar", width, styles["footer"])
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("j"), curses.KEY_DOWN):
            selected = min(len(names) - 1, selected + 1)
        elif key in (ord("k"), curses.KEY_UP):
            selected = max(0, selected - 1)
        elif key in (10, 13, curses.KEY_ENTER):
            return names[selected]
        elif key in (27, ord("q")):
            return current


def choose_suggestions(stdscr: curses.window, db: sqlite3.Connection, styles: dict[str, int]) -> list[Suggestion] | str:
    selected: set[int] = set()
    cursor = 0
    while True:
        height, width = stdscr.getmaxyx()
        subscribed = {url for feed in db.execute("SELECT site_url, feed_url FROM feeds")
                      for url in (feed["site_url"], feed["feed_url"])}
        stdscr.erase()
        draw(stdscr, 0, 0, " CLINEWS  /  sugestões de fontes", width, styles["header"] | curses.A_BOLD)
        draw(stdscr, 1, 1, "Escolha as fontes que quer acompanhar:", width - 2, styles["heading"])
        visible = max(1, height - 5)
        start = max(0, cursor - visible + 1)
        for row, suggestion in enumerate(SUGGESTIONS[start:start + visible], 2):
            index = start + row - 2
            saved = suggestion.feed_url in subscribed
            mark = "✓" if saved else "x" if index in selected else " "
            label = f" [{mark}] {suggestion.title}  ·  {suggestion.category}  ·  {suggestion.language}"
            attr = styles["selected"] if index == cursor else styles["muted"] if saved else styles["body"]
            draw(stdscr, row, 1, label, width - 2, attr)
        draw(stdscr, height - 2, 1, f"{len(selected)} selecionada(s)  ·  ✓ = já cadastrada", width - 2, styles["status"])
        draw(stdscr, height - 1, 0, " j/k mover  Espaço marcar  Enter adicionar  a link manual  Esc voltar", width, styles["footer"])
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("j"), curses.KEY_DOWN):
            cursor = min(len(SUGGESTIONS) - 1, cursor + 1)
        elif key in (ord("k"), curses.KEY_UP):
            cursor = max(0, cursor - 1)
        elif key == ord(" ") and SUGGESTIONS[cursor].feed_url not in subscribed:
            if cursor in selected:
                selected.remove(cursor)
            else:
                selected.add(cursor)
        elif key in (10, 13, curses.KEY_ENTER):
            if not selected and SUGGESTIONS[cursor].feed_url not in subscribed:
                selected.add(cursor)
            return [SUGGESTIONS[index] for index in sorted(selected)]
        elif key == ord("a"):
            return "manual"
        elif key in (27, ord("q")):
            return []


def add_manual(stdscr: curses.window, db: sqlite3.Connection, styles: dict[str, int]) -> str:
    url = prompt(stdscr, " URL do site ou RSS: ", styles)
    if not url:
        return "Cadastro cancelado."
    try:
        title, count = add_site(db, url)
        return f"{title}: {count} notícias adicionadas."
    except (ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
        return f"Erro: {exc}"


def add_suggestions(stdscr: curses.window, db: sqlite3.Connection,
                    styles: dict[str, int], selected: list[Suggestion]) -> str:
    added = 0
    articles = 0
    errors = []
    for index, suggestion in enumerate(selected, 1):
        height, width = stdscr.getmaxyx()
        draw(stdscr, height - 2, 1, f"Adicionando {index}/{len(selected)}: {suggestion.title}...", width - 2, styles["status"])
        stdscr.refresh()
        try:
            _, count = add_site(db, suggestion.feed_url, suggestion.title)
            added += 1
            articles += count
        except (ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
            errors.append(f"{suggestion.title}: {exc}")
    result = f"{added} fonte(s) adicionada(s), {articles} notícia(s)."
    if errors:
        result += f" {len(errors)} falha(s): {errors[0]}"
    return result


def ui(stdscr: curses.window, db: sqlite3.Connection, demo: bool) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    theme_name = load_theme()
    styles = apply_theme(stdscr, theme_name)
    selected_feed = 0
    selected_article = 0
    pane = 0
    status = "Prévia de demonstração: dados fictícios" if demo else "Pressione 's' para sugestões ou 'a' para colar um link."
    if not demo and not db.execute("SELECT 1 FROM feeds LIMIT 1").fetchone():
        choice = choose_suggestions(stdscr, db, styles)
        if choice == "manual":
            status = add_manual(stdscr, db, styles)
        elif choice:
            status = add_suggestions(stdscr, db, styles, choice)
    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()
        if height < 8 or width < 45:
            draw(stdscr, 0, 0, "Aumente o terminal (mínimo 45x8).", width)
            stdscr.refresh()
            if stdscr.getch() == ord("q"):
                return
            continue
        feeds = db.execute("SELECT * FROM feeds ORDER BY title").fetchall()
        selected_feed = min(selected_feed, len(feeds))
        feed_id = feeds[selected_feed - 1]["id"] if selected_feed else None
        if feed_id is None:
            articles = db.execute("SELECT a.*, f.title AS feed_title FROM articles a JOIN feeds f ON f.id=a.feed_id ORDER BY a.published DESC, a.id DESC").fetchall()
        else:
            articles = db.execute("SELECT a.*, f.title AS feed_title FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE feed_id=? ORDER BY a.published DESC, a.id DESC", (feed_id,)).fetchall()
        selected_article = max(0, min(selected_article, len(articles) - 1))
        unread = db.execute("SELECT COUNT(*) FROM articles WHERE is_read=0").fetchone()[0]
        draw(stdscr, 0, 0, f" CLINEWS  ●  {unread} não lidas  •  {theme_name}", width, styles["header"] | curses.A_BOLD)
        heading_row = 1
        first_row = 2
        left = max(18, min(29, width // 3))
        draw(stdscr, heading_row, 1, f"FONTES ({len(feeds)})", left - 2, styles["heading"] | curses.A_BOLD)
        draw(stdscr, heading_row, left + 1, f"NOTÍCIAS ({len(articles)})", width - left - 2, styles["heading"] | curses.A_BOLD)
        source_rows = [("Todas as fontes", None)] + [(feed["title"], feed["id"]) for feed in feeds]
        visible = height - first_row - 3
        source_start = max(0, selected_feed - visible + 1)
        for row, (title, source_id) in enumerate(source_rows[source_start:source_start + visible], first_row):
            count = db.execute("SELECT COUNT(*) FROM articles WHERE is_read=0" + (" AND feed_id=?" if source_id else ""),
                               (source_id,) if source_id else ()).fetchone()[0]
            label = f"{title[:left-9]:<{left-9}} {count:>3}"
            attr = styles["selected"] if pane == 0 and source_start + row - first_row == selected_feed else styles["body"]
            draw(stdscr, row, 1, label, left - 2, attr)
        start = max(0, selected_article - visible + 1)
        for row, article in enumerate(articles[start:start + visible], first_row):
            index = start + row - first_row
            marker = "●" if not article["is_read"] else " "
            available = width - left - 4
            label = f"{marker} {article['title']}"
            attr = styles["selected"] if pane == 1 and index == selected_article else (
                styles["unread"] | curses.A_BOLD if not article["is_read"] else styles["body"])
            draw(stdscr, row, left + 1, label, available, attr)
        draw(stdscr, height - 3, 1, "─" * max(0, width - 2), width - 2, styles["muted"])
        draw(stdscr, height - 2, 1, status, width - 2, styles["status"])
        footer = "Tab trocar  j/k mover  Enter ler  q sair" if width < 55 else (
            "Tab painel  j/k mover  Enter ler  r atualizar  t temas  q sair" if width < 80 else
            "Tab painel  j/k mover  Enter ler  s sugestões  a link  r atualizar  d remover  t temas  q sair"
        )
        draw(stdscr, height - 1, 0, footer, width, styles["footer"])
        stdscr.refresh()
        key = stdscr.getch()
        if key == ord("q"):
            return
        if key in (9, curses.KEY_RIGHT, curses.KEY_LEFT):
            pane = 1 - pane
        elif key in (ord("j"), curses.KEY_DOWN):
            if pane == 0:
                selected_feed = min(len(feeds), selected_feed + 1)
                selected_article = 0
            else:
                selected_article = min(max(0, len(articles) - 1), selected_article + 1)
        elif key in (ord("k"), curses.KEY_UP):
            if pane == 0:
                selected_feed = max(0, selected_feed - 1)
                selected_article = 0
            else:
                selected_article = max(0, selected_article - 1)
        elif key in (10, 13, curses.KEY_ENTER):
            if pane == 0:
                pane = 1
            elif articles:
                article = articles[selected_article]
                db.execute("UPDATE articles SET is_read=1 WHERE id=?", (article["id"],))
                db.commit()
                reader(stdscr, db, article, styles)
        elif key == ord("t"):
            chosen = choose_theme(stdscr, theme_name)
            styles = apply_theme(stdscr, chosen)
            if chosen != theme_name:
                try:
                    save_theme(chosen)
                    theme_name = chosen
                    status = f"Tema {chosen} salvo."
                except OSError as exc:
                    styles = apply_theme(stdscr, theme_name)
                    status = f"Não foi possível salvar o tema: {exc}"
        elif key == ord("a"):
            if demo:
                status = "No modo demonstração, alterações não são salvas."
                continue
            status = add_manual(stdscr, db, styles)
        elif key == ord("s"):
            choice = choose_suggestions(stdscr, db, styles)
            if choice == "manual":
                status = "No modo demonstração, alterações não são salvas." if demo else add_manual(stdscr, db, styles)
            elif choice:
                status = "No modo demonstração, alterações não são salvas." if demo else add_suggestions(stdscr, db, styles, choice)
        elif key == ord("r"):
            if demo:
                status = "Modo demonstração: nenhuma conexão feita."
            else:
                status = "Atualizando..."
                count, errors = refresh(db)
                status = f"{count} notícias novas." + (f" {len(errors)} fonte(s) com erro." if errors else "")
        elif key == ord("d") and pane == 0 and selected_feed > 0:
            feed = feeds[selected_feed - 1]
            answer = prompt(stdscr, f" Remover {feed['title']}? (s/N): ", styles)
            if answer.lower() == "s":
                db.execute("DELETE FROM articles WHERE feed_id=?", (feed["id"],))
                db.execute("DELETE FROM feeds WHERE id=?", (feed["id"],))
                db.commit()
                selected_feed = 0
                status = "Fonte removida."


def main() -> None:
    parser = argparse.ArgumentParser(description="Notícias dos sites que você escolhe, no terminal.")
    parser.add_argument("--demo", action="store_true", help="abre uma prévia com notícias fictícias")
    args = parser.parse_args()
    db = demo_db() if args.demo else open_db(data_path())
    try:
        curses.wrapper(ui, db, args.demo)
    finally:
        db.close()


if __name__ == "__main__":
    main()
