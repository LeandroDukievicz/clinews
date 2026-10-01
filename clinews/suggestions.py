"""Fontes sugeridas; nenhuma é adicionada sem a escolha da pessoa."""

from typing import NamedTuple


class Suggestion(NamedTuple):
    title: str
    category: str
    language: str
    feed_url: str


SUGGESTIONS = (
    Suggestion("Agência Brasil", "Notícias", "PT", "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"),
    Suggestion("Tecnoblog", "Tecnologia", "PT", "https://tecnoblog.net/feed/"),
    Suggestion("Manual do Usuário", "Tecnologia", "PT", "https://manualdousuario.net/feed/"),
    Suggestion("Olhar Digital", "Tecnologia", "PT", "https://olhardigital.com.br/feed/"),
    Suggestion("Agência Brasil: Economia", "Economia", "PT", "https://agenciabrasil.ebc.com.br/rss/economia/feed.xml"),
    Suggestion("Rádioagência: Cultura", "Cultura", "PT", "https://agenciabrasil.ebc.com.br/radioagencia-nacional/rss/cultura/feed.xml"),
    Suggestion("NASA", "Ciência", "EN", "https://www.nasa.gov/feed/"),
    Suggestion("ScienceDaily", "Ciência", "EN", "https://www.sciencedaily.com/rss/all.xml"),
    Suggestion("The Verge", "Tecnologia", "EN", "https://www.theverge.com/rss/index.xml"),
    Suggestion("Ars Technica", "Tecnologia", "EN", "https://arstechnica.com/feed/"),
)
