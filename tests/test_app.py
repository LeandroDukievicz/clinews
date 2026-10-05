import tempfile
import threading
import unittest
import io
import json
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError

from clinews.app import add_site, data_path, open_db, parse_feed, prompt, refresh
from clinews.themes import DEFAULT_THEME, THEMES, config_path, load_theme, nearest_xterm, save_theme, xterm_theme_color
from clinews.translation import TranslationError, split_for_api, translate_to_portuguese


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


class FakeWindow:
    """O mínimo de `curses.window` que `prompt` usa, para testar sem terminal."""

    def __init__(self, width, keys):
        self.width = width
        self.keys = list(keys)
        self.drawn = []

    def getmaxyx(self):
        return 24, self.width

    def addnstr(self, y, x, text, n, attr=0):
        self.drawn.append(text[:n])

    def move(self, y, x):
        pass

    def refresh(self):
        pass

    def get_wch(self):
        return self.keys.pop(0)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def fake_response(payload):
    def opener(request, timeout):
        return FakeResponse(json.dumps(payload).encode())
    return opener


class AppTest(unittest.TestCase):
    def test_readable_theme_contrast(self):
        def luminance(color):
            channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                      for value in channels]
            return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

        def contrast(first, second):
            light, dark = sorted((luminance(first), luminance(second)), reverse=True)
            return (light + 0.05) / (dark + 0.05)

        # `accent2` fica fora: nenhum papel de `apply_theme` o desenha na tela.
        for name, palette in THEMES.items():
            for role in ("fg", "muted", "accent", "unread", "link"):
                with self.subTest(theme=name, role=role):
                    self.assertGreaterEqual(contrast(palette[role], palette["bg"]), 4.5)
            with self.subTest(theme=name, role="selected_fg"):
                self.assertGreaterEqual(contrast(palette["selected_fg"], palette["selection"]), 4.5)
            for role in ("fg", "muted"):
                with self.subTest(theme=name, role=f"{role}/surface"):
                    self.assertGreaterEqual(contrast(palette[role], palette["surface"]), 4.5)

    # As paletas do WatchAI (src/watchai/theme.py), na ordem do seletor dele e
    # com as cores que o clinews usa: bg, bg2, cyan, cyan2, magenta, green,
    # text, muted. Copiadas à mão de propósito: é esta tabela que falha quando
    # um dos dois aplicativos mexe numa cor sem mexer no outro.
    WATCHAI_PALETTES = {
        "WatchAI": ("#05070D", "#080D16", "#00E5FF", "#00AFC8", "#FF2BD6", "#00FF85", "#D8E2F0", "#7C8799"),
        "Light": ("#FBFCFD", "#EFF2F6", "#0A7C8A", "#0E5D67", "#A626A4", "#1A7F37", "#1F2328", "#656D76"),
        "Dark": ("#0D1117", "#161B22", "#56B6C2", "#3E8A94", "#C678DD", "#56D364", "#E6EDF3", "#8B949E"),
        "Night Owl": ("#011627", "#0B2942", "#7FDBCA", "#21C7A8", "#C792EA", "#ADDB67", "#D6DEEB", "#8BA1B3"),
        "Vampire": ("#282A36", "#21222C", "#8BE9FD", "#BD93F9", "#FF79C6", "#50FA7B", "#F8F8F2", "#9AA0BF"),
        "Cyberpunk": ("#05010A", "#0D0418", "#00F0FF", "#00B8C4", "#FF00A0", "#00FF9F", "#F2E9FF", "#9A86BC"),
        "Steampunk": ("#140F0A", "#1F1811", "#7FB2A1", "#5A8A7C", "#C9762F", "#9FB055", "#EFE2CC", "#9A876C"),
        "Grey": ("#0E0E0E", "#171717", "#9C9C9C", "#7A7A7A", "#C2C2C2", "#DADADA", "#E8E8E8", "#8C8C8C"),
    }

    def test_themes_are_the_watchai_palettes(self):
        """Os temas são as oito paletas do WatchAI, nome por nome e cor por cor."""
        self.assertEqual(list(THEMES), list(self.WATCHAI_PALETTES))
        self.assertEqual(DEFAULT_THEME, "WatchAI")  # a paleta padrão do WatchAI
        for name, palette in self.WATCHAI_PALETTES.items():
            bg, bg2, cyan, cyan2, magenta, green, text, muted = palette
            with self.subTest(theme=name):
                self.assertEqual(THEMES[name], dict(
                    bg=bg, fg=text, surface=bg2, muted=muted,
                    accent=cyan, accent2=magenta, selection=cyan,
                    selected_fg=bg, unread=green,
                    # O cyan2 do Grey raspa o limite de contraste; lá o link usa
                    # o texto secundário da mesma paleta.
                    link="#BDBDBD" if name == "Grey" else cyan2,
                ))

    def test_header_stays_visible_in_256_colors(self):
        """Fundo e superfície não podem cair na mesma cor aproximada."""
        for name in THEMES:
            with self.subTest(theme=name):
                self.assertNotEqual(xterm_theme_color(name, "bg"),
                                    xterm_theme_color(name, "surface"))

    def test_translation_request_and_response(self):
        payload = {"responseStatus": 200, "responseData": {
            "translatedText": "Ciência &amp; tecnologia", "detectedLanguage": "en"}}
        pedidos = []

        def fake_open(request, timeout):
            self.assertEqual(timeout, 15)
            pedidos.append(request.full_url)
            return FakeResponse(json.dumps(payload).encode())

        with patch.dict("os.environ", {"CLINEWS_MYMEMORY_EMAIL": ""}), \
                patch("clinews.translation.load_email", return_value=""), \
                patch("clinews.translation.urlopen", side_effect=fake_open):
            titulo, resumo, idioma = translate_to_portuguese("Science & technology", "")
        self.assertEqual((titulo, resumo, idioma), ("Ciência & tecnologia", "", "EN"))
        self.assertIn("langpair=Autodetect%7Cpt-BR", pedidos[0])
        self.assertNotIn("de=", pedidos[0])  # sem e-mail, o parâmetro não vai

    def test_long_url_survives_a_narrow_terminal(self):
        """O endereço inteiro tem que voltar mesmo quando não cabe na linha."""
        url = "https://exemplo.com.br/secao/" + "a" * 60 + "/feed.xml"
        window = FakeWindow(width=80, keys=[*url, "\n"])
        with patch("curses.noecho"), patch("curses.curs_set"):
            typed = prompt(window, " URL do site ou RSS: ", {"footer": 0})
        self.assertEqual(typed, url)

    def test_prompt_cancels_with_escape(self):
        window = FakeWindow(width=80, keys=["h", "t", "t", "p", "\x1b"])
        with patch("curses.noecho"), patch("curses.curs_set"):
            self.assertEqual(prompt(window, " URL: ", {"footer": 0}), "")

    def test_translation_accepts_languages_other_than_english(self):
        payload = {"responseStatus": 200, "responseData": {
            "translatedText": "Uma manchete", "detectedLanguage": "de"}}
        with patch("clinews.translation.load_email", return_value=""), \
                patch("clinews.translation.urlopen", side_effect=fake_response(payload)):
            _, _, detected = translate_to_portuguese("Eine Schlagzeile",
                                                     "Eine ausreichend lange Zusammenfassung.")
        self.assertEqual(detected, "DE")

    def test_translation_refuses_text_already_in_portuguese(self):
        """E recusa antes de gastar cota com os pedaços restantes."""
        payload = {"responseStatus": 200, "responseData": {
            "translatedText": "Uma manchete", "detectedLanguage": "pt"}}
        chamadas = []

        def contar(request, timeout):
            chamadas.append(request.full_url)
            return fake_response(payload)(request, timeout)

        with patch("clinews.translation.load_email", return_value=""), \
                patch("clinews.translation.urlopen", side_effect=contar):
            with self.assertRaisesRegex(TranslationError, "já está em português"):
                translate_to_portuguese("Uma manchete",
                                        "Um resumo qualquer, bem mais longo que o titulo.")
        self.assertEqual(len(chamadas), 1)

    def test_translation_sends_the_optional_email(self):
        """O e-mail vai no parâmetro `de`, que é o que amplia a cota diária."""
        payload = {"responseStatus": 200, "responseData": {
            "translatedText": "Oi", "detectedLanguage": "en"}}
        urls = []

        def capture(request, timeout):
            urls.append(request.full_url)
            return fake_response(payload)(request, timeout)

        with patch("clinews.translation.load_email", return_value=""), \
                patch("clinews.translation.urlopen", side_effect=capture):
            translate_to_portuguese("Hi", "", "eu@exemplo.com")
        self.assertIn("de=eu%40exemplo.com", urls[0])

    def test_translation_explains_an_exhausted_quota(self):
        payload = {"responseStatus": 403, "quotaFinished": True,
                   "responseDetails": "YOU USED ALL AVAILABLE FREE TRANSLATIONS FOR TODAY",
                   "responseData": {"translatedText": "", "detectedLanguage": None}}
        with patch("clinews.translation.load_email", return_value=""), \
                patch("clinews.translation.urlopen", side_effect=fake_response(payload)):
            with self.assertRaisesRegex(TranslationError, "cota diária"):
                translate_to_portuguese("Hello", "")

    def test_translation_reports_a_refusal(self):
        payload = {"responseStatus": 403, "responseDetails": "INVALID EMAIL PROVIDED",
                   "responseData": {"translatedText": "", "detectedLanguage": None}}
        with patch("clinews.translation.load_email", return_value=""), \
                patch("clinews.translation.urlopen", side_effect=fake_response(payload)):
            with self.assertRaisesRegex(TranslationError, "INVALID EMAIL PROVIDED"):
                translate_to_portuguese("Hello", "")

    def test_summary_is_split_under_the_api_limit(self):
        """A API recusa acima de 500 caracteres: nenhum pedaço pode passar disso."""
        frase = "Os pesquisadores publicaram uma analise detalhada das galaxias distantes. "
        resumo = (frase * 12).strip()
        self.assertGreater(len(resumo), 500)
        for pedaco in split_for_api(resumo):
            with self.subTest(pedaco=pedaco[:40]):
                self.assertLessEqual(len(pedaco), 500)
                self.assertTrue(pedaco.strip())
        # nada se perde na quebra
        self.assertEqual(" ".join(split_for_api(resumo)).split(), resumo.split())

    def test_split_breaks_a_word_longer_than_the_limit(self):
        """Um endereço colado no resumo nao tem espaco onde cortar."""
        gigante = "https://exemplo.com/" + "x" * 900
        pedacos = split_for_api(gigante)
        self.assertGreater(len(pedacos), 1)
        for pedaco in pedacos:
            self.assertLessEqual(len(pedaco), 500)
        self.assertEqual("".join(pedacos), gigante)

    def test_summary_keeps_its_paragraphs(self):
        """O resumo volta com as mesmas linhas que o feed mandou."""
        payload = {"responseStatus": 200, "responseData": {
            "translatedText": "traduzido", "detectedLanguage": "en"}}
        with patch("clinews.translation.load_email", return_value=""), \
                patch("clinews.translation.urlopen", side_effect=fake_response(payload)):
            _, resumo, _ = translate_to_portuguese("Title", "First line.\nSecond line.")
        self.assertEqual(resumo.splitlines(), ["traduzido", "traduzido"])

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
        self.assertEqual(xterm_theme_color("WatchAI", "accent"), 45)
        self.assertEqual(xterm_theme_color("Cyberpunk", "accent"), 51)
        self.assertEqual(xterm_theme_color("Grey", "surface"), 234)

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
