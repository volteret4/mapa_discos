"""Normalización para cruzar la discografía de MusicBrainz con la colección
(musica_local.sqlite) y para agrupar géneros escritos de formas distintas."""
import re
import unicodedata

_EDITION_SUFFIX = re.compile(
    r"\s*[\(\[][^\)\]]*(edition|deluxe|remaster|version|reissue|expanded|anniversary|bonus|edición)[^\)\]]*[\)\]]",
    re.I,
)
_LEADING_THE = re.compile(r"^the\s+")
_NON_WORD = re.compile(r"[^\w]")
_GENRE_SPLIT = re.compile(r"\s*[,;/]\s*")
_YEAR = re.compile(r"\s*(\d{4})")

IGNORED_GENRES = {"", "unknown", "other", "misc", "genre"}


def normalize_title(title):
    """Mayúsculas, acentos, 'The ', puntuación y sufijos de edición fuera:
    "OK Computer (Deluxe Edition)" == "ok computer"."""
    s = _EDITION_SUFFIX.sub("", title or "").strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return _NON_WORD.sub("", _LEADING_THE.sub("", s))


def genre_key(genre):
    """"Post-Rock", "post rock" y "post_rock" son el mismo género."""
    return re.sub(r"[\s_\-]+", " ", (genre or "").strip().lower())


def split_genres(text):
    return [g for g in _GENRE_SPLIT.split(text or "") if genre_key(g) not in IGNORED_GENRES]


def year_of(value):
    m = _YEAR.match(str(value or ""))
    return m.group(1) if m else ""
