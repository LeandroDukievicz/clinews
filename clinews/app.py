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

USER_AGENT = "clinews/0.1 (+terminal RSS reader)"
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
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "clinews" / "clinews.db"


def open_db(path: Path | str = ":memory:") -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
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


def add_site(db: sqlite3.Connection, url: str) -> tuple[str, int]:
    url = checked_url(url)
    feed_url, title, articles = discover_feed(url)
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
            title, articles = parse_feed(data, final_url)
            db.execute("UPDATE feeds SET title = ?, feed_url = ? WHERE id = ?", (title, final_url, feed["id"]))
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


def prompt(stdscr: curses.window, label: str) -> str:
    height, width = stdscr.getmaxyx()
    label = label[:max(1, width - 2)]
    curses.echo()
    curses.curs_set(1)
    draw(stdscr, height - 1, 0, label, width, curses.A_REVERSE)
    stdscr.refresh()
    try:
        value = stdscr.getstr(height - 1, min(len(label), width - 1), max(1, width - len(label) - 1))
        return value.decode("utf-8", errors="replace").strip()
    finally:
        curses.noecho()
        curses.curs_set(0)


def reader(stdscr: curses.window, article: sqlite3.Row) -> None:
    lines = [article["title"], "", article["published"], ""]
    for paragraph in article["summary"].splitlines() or ["Sem resumo no feed. Abra o link para ler o texto completo."]:
        lines.extend(textwrap.wrap(paragraph, width=max(20, stdscr.getmaxyx()[1] - 4)) or [""])
    lines.extend(["", "Link da matéria original:"])
    lines.extend(textwrap.wrap(article["url"], width=max(20, stdscr.getmaxyx()[1] - 4),
                               break_long_words=True, break_on_hyphens=False)
                 if article["url"] else ["Não informado pelo feed."])
    offset = 0
    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()
        draw(stdscr, 0, 0, " clinews  /  leitura", width, curses.A_REVERSE)
        for row, line in enumerate(lines[offset:offset + height - 3], 1):
            draw(stdscr, row, 2, line, max(1, width - 4), curses.A_BOLD if row == 1 and offset == 0 else 0)
        draw(stdscr, height - 1, 0, " j/k rolar   o abrir link   q voltar", width, curses.A_REVERSE)
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


def ui(stdscr: curses.window, db: sqlite3.Connection, demo: bool) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    selected_feed = 0
    selected_article = 0
    pane = 0
    status = "Prévia de demonstração: dados fictícios" if demo else "Cole um site com 'a' para começar."
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
        draw(stdscr, 0, 0, f" CLINEWS  ●  {unread} não lidas", width, curses.A_REVERSE | curses.A_BOLD)
        expanded_header = height >= 14 and width >= 70
        if expanded_header:
            draw(stdscr, 1, 2, "  ▄▄▄▄▄", width - 4)
            draw(stdscr, 2, 2, " ▐▣ ▣▣▌    C L I N E W S", width - 4, curses.A_BOLD)
            draw(stdscr, 3, 2, " ▐▄▄▄▄▌    Notícias dos sites que você escolhe", width - 4)
        heading_row = 5 if expanded_header else 2
        first_row = heading_row + 1
        left = max(18, min(29, width // 3))
        draw(stdscr, heading_row, 1, "FONTES", left - 2, curses.A_BOLD)
        draw(stdscr, heading_row, left + 1, "NOTÍCIAS", width - left - 2, curses.A_BOLD)
        source_rows = [("Todas as fontes", None)] + [(feed["title"], feed["id"]) for feed in feeds]
        visible = height - first_row - 3
        source_start = max(0, selected_feed - visible + 1)
        for row, (title, source_id) in enumerate(source_rows[source_start:source_start + visible], first_row):
            count = db.execute("SELECT COUNT(*) FROM articles WHERE is_read=0" + (" AND feed_id=?" if source_id else ""),
                               (source_id,) if source_id else ()).fetchone()[0]
            label = f"{title[:left-9]:<{left-9}} {count:>3}"
            attr = curses.A_REVERSE if pane == 0 and source_start + row - first_row == selected_feed else 0
            draw(stdscr, row, 1, label, left - 2, attr)
        start = max(0, selected_article - visible + 1)
        for row, article in enumerate(articles[start:start + visible], first_row):
            index = start + row - first_row
            marker = "●" if not article["is_read"] else " "
            available = width - left - 4
            label = f"{marker} {article['title']}"
            attr = curses.A_REVERSE if pane == 1 and index == selected_article else (curses.A_BOLD if not article["is_read"] else 0)
            draw(stdscr, row, left + 1, label, available, attr)
        draw(stdscr, height - 3, 1, "─" * max(0, width - 2), width - 2)
        draw(stdscr, height - 2, 1, status, width - 2)
        draw(stdscr, height - 1, 0, " Tab painel   j/k mover   Enter ler   a adicionar   r atualizar   d remover   q sair", width, curses.A_REVERSE)
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
                reader(stdscr, article)
        elif key == ord("a"):
            if demo:
                status = "No modo demonstração, alterações não são salvas."
                continue
            url = prompt(stdscr, " URL do site ou RSS: ")
            if url:
                status = "Buscando RSS..."
                try:
                    title, count = add_site(db, url)
                    status = f"{title}: {count} notícias adicionadas."
                except (ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
                    status = f"Erro: {exc}"
        elif key == ord("r"):
            if demo:
                status = "Modo demonstração: nenhuma conexão feita."
            else:
                status = "Atualizando..."
                count, errors = refresh(db)
                status = f"{count} notícias novas." + (f" {len(errors)} fonte(s) com erro." if errors else "")
        elif key == ord("d") and pane == 0 and selected_feed > 0:
            feed = feeds[selected_feed - 1]
            answer = prompt(stdscr, f" Remover {feed['title']}? (s/N): ")
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
