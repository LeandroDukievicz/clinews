import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from clinews.app import add_site, data_path, open_db, parse_feed, refresh
from clinews.themes import DEFAULT_THEME, THEMES, config_path, load_theme, nearest_xterm, save_theme


RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Noticias de Teste</title>
<item><guid>n1</guid><title>Primeira noticia</title><link>/noticia/1</link>
<description>&lt;p&gt;Resumo de teste.&lt;/p&gt;</description><pubDate>Thu, 01 Oct 2026 09:00:00 GMT</pubDate></item>
</channel></rss>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = b'<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>'
            content_type = "text/html"
        elif self.path == "/feed.xml":
            body = RSS
            content_type = "application/rss+xml"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class AppTest(unittest.TestCase):
    def test_snap_uses_persistent_user_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict("os.environ", {"SNAP_USER_COMMON": temp, "XDG_DATA_HOME": "/not-used",
                                            "XDG_CONFIG_HOME": "/not-used"}):
                self.assertEqual(data_path(), Path(temp) / "data" / "clinews.db")
                self.assertEqual(config_path(), Path(temp) / "config" / "config.json")

    def test_theme_preference_persists(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            self.assertEqual(load_theme(path), DEFAULT_THEME)
            for name in THEMES:
                save_theme(name, path)
                self.assertEqual(load_theme(path), name)
            path.write_text('{"theme":"desconhecido"}', encoding="utf-8")
            self.assertEqual(load_theme(path), DEFAULT_THEME)

    def test_xterm_color_approximation(self):
        self.assertEqual(nearest_xterm("#000000"), 16)
        self.assertEqual(nearest_xterm("#FFFFFF"), 231)

    def test_atom_feed(self):
        atom = b'''<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Teste</title>
        <entry><id>urn:1</id><title>Artigo Atom</title><link href="/post/1"/>
        <summary type="html">&lt;p&gt;Texto Atom&lt;/p&gt;</summary>
        <updated>2026-10-01T10:00:00Z</updated></entry></feed>'''
        title, articles = parse_feed(atom, "https://exemplo.org/feed.xml")
        self.assertEqual(title, "Atom Teste")
        self.assertEqual(articles[0]["url"], "https://exemplo.org/post/1")
        self.assertEqual(articles[0]["summary"], "Texto Atom")

    def test_discovers_saves_and_deduplicates(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "clinews.db"
                db = open_db(path)
                site = f"http://127.0.0.1:{server.server_port}/"
                title, count = add_site(db, site, "Fonte sugerida")
                self.assertEqual((title, count), ("Fonte sugerida", 1))
                self.assertEqual(db.execute("SELECT summary FROM articles").fetchone()[0], "Resumo de teste.")
                self.assertEqual(add_site(db, site, "Fonte sugerida"), ("Fonte sugerida", 0))
                self.assertEqual(refresh(db), (0, []))
                self.assertEqual(db.execute("SELECT title FROM feeds").fetchone()[0], "Fonte sugerida")
                db.close()
                reopened = open_db(path)
                self.assertEqual(reopened.execute("SELECT COUNT(*) FROM feeds").fetchone()[0], 1)
                self.assertEqual(reopened.execute("SELECT COUNT(*) FROM articles").fetchone()[0], 1)
                reopened.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
