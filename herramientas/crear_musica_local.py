#!/usr/bin/env python3
"""Crea (o pone al día) una musica_local.sqlite mínima a partir de una carpeta de música.

mapa_discos lee tres tablas: artists, albums y musicbrainz_discography. Si ya usas
music-fuzzy, su base vale tal cual y no necesitas esto. Si no, este script las rellena:

  1. Recorre la carpeta y lee las etiquetas (artista del álbum, álbum, fecha, género y,
     si están, los identificadores de MusicBrainz que pone Picard).
  2. Con --musicbrainz, baja de MusicBrainz la discografía (álbumes y EP) de cada artista,
     para que el mapa enseñe también los discos que te faltan. Va a 1 consulta por segundo,
     como pide MusicBrainz: unos 2 s por artista, y lo ya bajado no se repite.

Uso:
    python3 crear_musica_local.py /ruta/a/tu/musica musica_local.sqlite
    python3 crear_musica_local.py /ruta/a/tu/musica musica_local.sqlite --musicbrainz

Volver a lanzarlo añade lo nuevo: los discos que ya no están pasan a «antiguo_local».
"""
import argparse
import os
import re
import sqlite3
import sys
import time

import mutagen
import requests

DISC_DIR = re.compile(r"^(cd|dis[ck]|disco)\W*\d+", re.I)
AUDIO = (".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wv", ".ape", ".aiff", ".aif", ".dsf")
MB = "https://musicbrainz.org/ws/2"
UA = {"User-Agent": "mapa_discos-crear_musica_local/1.0 ( https://github.com/volteret4/mapa_discos )"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY, name TEXT UNIQUE, origen TEXT, origin TEXT,
    formed_year INTEGER, tags TEXT, img_urls TEXT, mbid TEXT
);
CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY, artist_id INTEGER, name TEXT, year TEXT,
    originalyear INTEGER, genre TEXT, origen TEXT, mbid TEXT, path TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS musicbrainz_discography (
    id INTEGER PRIMARY KEY, artist_id INTEGER, album_id INTEGER, mbid TEXT,
    title TEXT, release_type TEXT, first_release_date TEXT, secondary_types TEXT,
    UNIQUE (artist_id, mbid)
);
CREATE TABLE IF NOT EXISTS mb_artistas_hechos (artist_id INTEGER PRIMARY KEY, fecha REAL);
"""


def first(tags, *keys):
    for k in keys:
        v = tags.get(k)
        if isinstance(v, list):
            v = v[0] if v else None
        if v:
            return str(v).strip()
    return ""


def year(text):
    text = (text or "")[:4]
    return int(text) if text.isdigit() else None


def scan(music_dir):
    """{carpeta: {artista, álbum, …}} con las etiquetas de la primera canción de cada carpeta."""
    albums = {}
    for root, dirs, files in os.walk(music_dir):
        dirs.sort()
        audio = sorted(f for f in files if f.lower().endswith(AUDIO))
        # «Disc 2», «CD1»…: el disco es la carpeta de encima
        key = os.path.dirname(root) if DISC_DIR.match(os.path.basename(root)) else root
        if not audio or key in albums:
            continue
        try:
            tags = mutagen.File(os.path.join(root, audio[0]), easy=True) or {}
        except Exception:
            continue
        artist = first(tags, "albumartist", "artist")
        album = first(tags, "album")
        if not (artist and album):
            continue
        albums[key] = {
            "artist": artist, "album": album,
            "date": first(tags, "date"), "original": first(tags, "originaldate", "originalyear"),
            "genre": first(tags, "genre"),
            "mbid": first(tags, "musicbrainz_albumid"),
            "artist_mbid": first(tags, "musicbrainz_albumartistid", "musicbrainz_artistid"),
        }
    return albums


def save_local(con, albums):
    con.execute("UPDATE albums SET origen = 'antiguo_local' WHERE origen = 'local'")
    for path, a in albums.items():
        con.execute("INSERT INTO artists (name, origen, mbid) VALUES (?, 'local', ?) "
                    "ON CONFLICT(name) DO UPDATE SET origen = 'local', mbid = COALESCE(artists.mbid, excluded.mbid)",
                    (a["artist"], a["artist_mbid"] or None))
        artist_id = con.execute("SELECT id FROM artists WHERE name = ?", (a["artist"],)).fetchone()[0]
        con.execute("""INSERT INTO albums (artist_id, name, year, originalyear, genre, origen, mbid, path)
                       VALUES (?, ?, ?, ?, ?, 'local', ?, ?)
                       ON CONFLICT(path) DO UPDATE SET artist_id = excluded.artist_id, name = excluded.name,
                         year = excluded.year, originalyear = excluded.originalyear, genre = excluded.genre,
                         origen = 'local', mbid = excluded.mbid""",
                    (artist_id, a["album"], a["date"], year(a["original"]), a["genre"], a["mbid"] or None, path))
    # Artistas que ya no tienen ningún disco presente
    con.execute("""UPDATE artists SET origen = 'antiguo_local' WHERE id NOT IN
                   (SELECT artist_id FROM albums WHERE origen = 'local')""")
    con.commit()


def mb_get(path, **params):
    time.sleep(1.1)
    r = requests.get(f"{MB}/{path}", params={**params, "fmt": "json"}, headers=UA, timeout=30)
    r.raise_for_status()
    return r.json()


def artist_mbid(con, artist_id, name, mbid):
    if mbid:
        return mbid
    hits = mb_get("artist", query=f'artist:"{name}"', limit=3).get("artists", [])
    best = next((h for h in hits if h.get("score", 0) >= 95 and h["name"].casefold() == name.casefold()), None)
    if best:
        con.execute("UPDATE artists SET mbid = ? WHERE id = ?", (best["id"], artist_id))
        return best["id"]
    return None


def fetch_discographies(con, refresh_days):
    pending = con.execute("""SELECT a.id, a.name, a.mbid FROM artists a
                             LEFT JOIN mb_artistas_hechos h ON h.artist_id = a.id
                             WHERE a.origen = 'local' AND (h.fecha IS NULL OR h.fecha < ?)
                             ORDER BY a.name""", (time.time() - refresh_days * 86400,)).fetchall()
    for n, (artist_id, name, mbid) in enumerate(pending, 1):
        print(f"[{n}/{len(pending)}] {name}", flush=True)
        try:
            mbid = artist_mbid(con, artist_id, name, mbid)
            if not mbid:
                print("   sin coincidencia clara en MusicBrainz", flush=True)
            else:
                info = mb_get(f"artist/{mbid}", inc="tags")
                tags = ", ".join(t["name"] for t in sorted(info.get("tags", []), key=lambda t: -t.get("count", 0))[:8])
                con.execute("UPDATE artists SET origin = ?, formed_year = ?, tags = COALESCE(NULLIF(?, ''), tags) "
                            "WHERE id = ?", ((info.get("area") or {}).get("name"),
                                             year((info.get("life-span") or {}).get("begin")), tags, artist_id))
                offset = 0
                while True:
                    page = mb_get("release-group", artist=mbid, type="album|ep", limit=100, offset=offset)
                    for rg in page.get("release-groups", []):
                        con.execute("""INSERT OR REPLACE INTO musicbrainz_discography
                                       (artist_id, mbid, title, release_type, first_release_date, secondary_types)
                                       VALUES (?, ?, ?, ?, ?, ?)""",
                                    (artist_id, rg["id"], rg["title"], rg.get("primary-type"),
                                     rg.get("first-release-date"), ", ".join(rg.get("secondary-types") or [])))
                    offset += 100
                    if offset >= page.get("release-group-count", 0):
                        break
            con.execute("INSERT OR REPLACE INTO mb_artistas_hechos VALUES (?, ?)", (artist_id, time.time()))
            con.commit()
        except requests.RequestException as e:
            print(f"   error de red, se reintentará la próxima vez: {e}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("music_dir", help="carpeta con tu música (un disco por carpeta)")
    ap.add_argument("db", help="fichero musica_local.sqlite que se crea o actualiza")
    ap.add_argument("--musicbrainz", action="store_true", help="bajar también la discografía de cada artista")
    ap.add_argument("--refrescar-dias", type=int, default=90,
                    help="volver a bajar la discografía de un artista pasados estos días (90)")
    args = ap.parse_args()
    if not os.path.isdir(args.music_dir):
        sys.exit(f"No existe la carpeta {args.music_dir}")
    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)
    albums = scan(args.music_dir)
    save_local(con, albums)
    print(f"{len(albums)} discos de {len({a['artist'] for a in albums.values()})} artistas", flush=True)
    if args.musicbrainz:
        fetch_discographies(con, args.refrescar_dias)
    con.close()


if __name__ == "__main__":
    main()
