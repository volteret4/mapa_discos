import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db as db_module  # noqa: E402
import discografia  # noqa: E402


@pytest.fixture
def musica_local_path(tmp_path, monkeypatch):
    path = tmp_path / "musica_local.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE artists (
            id INTEGER PRIMARY KEY, name TEXT, origen TEXT, origin TEXT,
            formed_year INTEGER, tags TEXT, img_urls TEXT
        );
        CREATE TABLE albums (
            id INTEGER PRIMARY KEY, artist_id INTEGER, name TEXT, year TEXT,
            originalyear INTEGER, genre TEXT, origen TEXT, mbid TEXT
        );
        CREATE TABLE musicbrainz_discography (
            id INTEGER PRIMARY KEY, artist_id INTEGER, album_id INTEGER, mbid TEXT,
            title TEXT, release_type TEXT, first_release_date TEXT, secondary_types TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO artists VALUES (?,?,?,?,?,?,?)",
        [
            (1, "Radiohead", "local", "United Kingdom", 1991, "rock",
             '[{"url": "https://i.discogs.com/r.jpg"}, {"url": "https://i.scdn.co/image/ab67616100005174aa"}]'),
            (2, "PJ Harvey", "local", "England", 1969, "rock", '["https://i.scdn.co/image/pj"]'),
            (3, "Gente Que Ya No Está", "antiguo_local", None, None, "art rock", None),
            (4, "Sin Discografía", "local", None, None, None, None),
        ],
    )
    conn.executemany(
        "INSERT INTO albums VALUES (?,?,?,?,?,?,?,?)",
        [
            (10, 1, "OK Computer (Deluxe Edition)", "1997", None, "Alternative Rock", "local", "rel-okc"),
            (11, 1, "Kid A", "2000", None, "Alternative Rock, Art Rock", "local", None),
            (12, 1, "Live Recordings 1995", "2017", None, "Unknown", "local", None),
            (13, 1, "Amnesiac", "2001", None, "alternative-rock", "antiguo_local", None),
            (20, 2, "Rid of Me", "1993", None, "Alternative Rock", "local", None),
            (21, 2, "Dry", "1992", None, "Alternative Rock", "local", None),
            (30, 3, "Viejo", "1980", None, "Art Rock", "antiguo_local", None),
            (40, 4, "Disco Suelto", "2010-05-01", None, "Rock", "local", None),
        ],
    )
    conn.executemany(
        "INSERT INTO musicbrainz_discography VALUES (?,?,?,?,?,?,?,?)",
        [
            (1, 1, None, "rg-pablo", "Pablo Honey", "Album", "1993-02-22", None),
            (2, 1, None, "rg-okc", "OK Computer", "Album", "1997-05-21", None),
            (3, 1, 11, "rg-kida", "Kid A", "Album", "2000-10-02", None),
            (4, 1, None, "rg-amn", "Amnesiac", "Album", "2001-06-04", None),
            (5, 1, None, "rg-live", "I Might Be Wrong", "Album", "2001-11-12", "Live"),
            (6, 1, None, "rg-ep", "My Iron Lung", "EP", "1994-09-26", ""),
            (7, 1, None, "rg-single", "Creep", "Single", "1992-09-21", None),
            (8, 2, None, "rg-dry", "Dry", "Album", "1992-03-30", None),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db_module, "MUSICA_LOCAL_DB", str(path))
    monkeypatch.setattr(discografia, "_GENRE_INDEX", None)
    return str(path)


@pytest.fixture
def client(musica_local_path):
    import server
    server.app.config["TESTING"] = True
    return server.app.test_client()
