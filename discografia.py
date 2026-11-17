"""Consultas del mapa: discografía de un artista cruzada con la colección,
géneros de su discografía y otros artistas de un género.

- Discografía completa: tabla musicbrainz_discography de musica_local.sqlite.
- Lo que poseemos: tabla albums (origen 'local'; 'antiguo_local' si los
  archivos ya no están).
- "Original": mismo criterio que discografia-gaps -- release-groups Album/EP
  sin secondary-types de directo, recopilatorio, remix, BSO...
"""
import json
import threading
from collections import Counter, defaultdict

from db import get_musica_local_conn
from normalize import genre_key, normalize_title, split_genres, year_of

LOCAL = "local"
OLD_LOCAL = "antiguo_local"

# Igual que discografia-gaps/clients/musicbrainz_client.py
EXCLUDED_SECONDARY_TYPES = {
    "Live", "Compilation", "Remix", "DJ-mix", "Mixtape/Street",
    "Soundtrack", "Interview", "Audiobook", "Spokenword", "Demo",
}

CAA = "https://coverartarchive.org"


def _state(origen):
    return {LOCAL: "local", OLD_LOCAL: "antiguo"}.get(origen)


def _artist_images(img_urls):
    # img_urls viene en dos formatos: ["url", ...] o [{"url": ..., "path": ...}, ...]
    try:
        items = json.loads(img_urls or "[]")
    except ValueError:
        return []
    urls = [i.get("url") if isinstance(i, dict) else i for i in items if isinstance(i, (dict, str))]
    urls = [u for u in urls if u and u.startswith("http")]
    # Spotify primero (y su tamaño de 320 px): Discogs a veces bloquea el
    # hotlinking. La web prueba en orden hasta que una carga.
    urls.sort(key=lambda u: ("scdn.co" not in u, "ab67616100005174" not in u))
    return urls[:3]


def _covers(release_group_mbid=None, release_mbid=None):
    # La del release-group primero: Cover Art Archive no tiene portada de
    # todas las ediciones concretas (o devuelve 404/500 en algunas).
    covers = []
    if release_group_mbid:
        covers.append(f"{CAA}/release-group/{release_group_mbid}/front-250")
    if release_mbid:
        covers.append(f"{CAA}/release/{release_mbid}/front-250")
    return covers


def search(q, limit=20):
    """Artistas, discos de la colección y discos de MusicBrainz que contengan
    `q`; primero los que empiezan por `q`."""
    q = (q or "").strip()
    if len(q) < 2:
        return []
    like, prefix = f"%{q}%", f"{q.lower()}%"
    results = []
    with get_musica_local_conn() as conn:
        for r in conn.execute(
                "SELECT id, name, origen FROM artists WHERE name LIKE ? "
                "ORDER BY lower(name) NOT LIKE ?, length(name) LIMIT ?", (like, prefix, limit)):
            results.append({"type": "artist", "artist_id": r["id"], "label": r["name"],
                            "state": _state(r["origen"])})
        for r in conn.execute(
                "SELECT al.id, al.name, al.origen, ar.id AS artist_id, ar.name AS artist "
                "FROM albums al JOIN artists ar ON ar.id = al.artist_id WHERE al.name LIKE ? "
                "ORDER BY lower(al.name) NOT LIKE ?, length(al.name) LIMIT ?", (like, prefix, limit)):
            results.append({"type": "album", "artist_id": r["artist_id"], "album_key": f"a{r['id']}",
                            "label": r["name"], "artist": r["artist"], "state": _state(r["origen"])})
        for r in conn.execute(
                "SELECT md.mbid, md.title, ar.id AS artist_id, ar.name AS artist "
                "FROM musicbrainz_discography md JOIN artists ar ON ar.id = md.artist_id "
                "WHERE md.title LIKE ? AND md.release_type IN ('Album', 'EP') "
                "ORDER BY lower(md.title) NOT LIKE ?, length(md.title) LIMIT ?", (like, prefix, limit)):
            results.append({"type": "album", "artist_id": r["artist_id"], "album_key": r["mbid"],
                            "label": r["title"], "artist": r["artist"], "state": None})
    # Un disco que tenemos aparece también como título de MusicBrainz
    seen, unique = set(), []
    for r in results:
        key = (r["type"], r["artist_id"], normalize_title(r["label"]))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda r: (not r["label"].lower().startswith(q.lower()), r["type"] != "artist"))
    return unique[:limit]


def _match_owned(norm, by_album_id, by_norm):
    if by_album_id:
        return by_album_id
    if not norm:
        return None
    if norm in by_norm:
        return by_norm[norm]
    # "When the Pawn" frente a "When the Pawn Hits the Conflicts...", etc.
    for owned_norm, owned in by_norm.items():
        if min(len(owned_norm), len(norm)) >= 6 and (owned_norm.startswith(norm) or norm.startswith(owned_norm)):
            return owned
    return None


def artist(artist_id):
    """Ficha del artista con sus álbumes originales, EPs, discos propios sin
    ficha en MusicBrainz y géneros. None si no existe."""
    with get_musica_local_conn() as conn:
        a = conn.execute(
            "SELECT id, name, origen, origin, formed_year, img_urls FROM artists WHERE id = ?",
            (artist_id,)).fetchone()
        if not a:
            return None
        owned = []
        for r in conn.execute(
                "SELECT id, name, year, originalyear, origen, mbid FROM albums WHERE artist_id = ?",
                (artist_id,)):
            if r["origen"] not in (LOCAL, OLD_LOCAL):
                continue
            owned.append({"album_id": r["id"], "title": r["name"], "norm": normalize_title(r["name"]),
                          "year": year_of(r["originalyear"]) or year_of(r["year"]),
                          "state": _state(r["origen"]), "mbid": r["mbid"] or None})
        mb_rows = conn.execute(
            "SELECT mbid, title, release_type, secondary_types, first_release_date, album_id "
            "FROM musicbrainz_discography WHERE artist_id = ? ORDER BY first_release_date",
            (artist_id,)).fetchall()

    # Si hay varias copias del mismo disco, manda la que sigue en local
    owned.sort(key=lambda o: o["state"] != "local")
    by_id = {o["album_id"]: o for o in owned}
    by_norm = {}
    for o in owned:
        by_norm.setdefault(o["norm"], o)

    sections = {"Album": [], "EP": []}
    used, seen = set(), set()
    for r in mb_rows:
        norm = normalize_title(r["title"])
        match = _match_owned(norm, by_id.get(r["album_id"]), by_norm)
        if match:
            used.add(match["album_id"])
        secondary = {s.strip() for s in (r["secondary_types"] or "").split(",") if s.strip()}
        release_type = r["release_type"]
        if release_type not in sections or secondary & EXCLUDED_SECONDARY_TYPES:
            continue
        if (release_type, norm) in seen:
            continue
        seen.add((release_type, norm))
        sections[release_type].append({
            "key": r["mbid"] or (f"a{match['album_id']}" if match else f"t{norm}"),
            "album_id": match["album_id"] if match else None,
            "title": r["title"],
            "year": year_of(r["first_release_date"]),
            "date": r["first_release_date"] or "",
            "kind": release_type,
            "detail": release_type if not secondary else f"{release_type} ({', '.join(sorted(secondary))})",
            "state": match["state"] if match else None,
            "owned_title": match["title"] if match else None,
            "covers": _covers(r["mbid"], match["mbid"] if match else None),
            "url": f"https://musicbrainz.org/release-group/{r['mbid']}" if r["mbid"] else None,
        })

    def own_entry(o, detail):
        return {
            "key": f"a{o['album_id']}", "album_id": o["album_id"], "title": o["title"], "year": o["year"], "date": "",
            "kind": "Propio", "detail": detail, "state": o["state"], "owned_title": o["title"],
            "covers": _covers(release_mbid=o["mbid"]),
            "url": f"https://musicbrainz.org/release/{o['mbid']}" if o["mbid"] else None,
        }

    has_mb = bool(mb_rows)
    if has_mb:
        albums, eps = sections["Album"], sections["EP"]
        extra = [own_entry(o, "Sin ficha en MusicBrainz") for o in owned if o["album_id"] not in used]
    else:
        albums = sorted((own_entry(o, "En tu colección") for o in owned),
                        key=lambda r: (r["year"] or "9999", r["title"].lower()))
        eps, extra = [], []

    return {
        "artist": {
            "id": a["id"], "name": a["name"], "state": _state(a["origen"]),
            "origin": a["origin"], "formed_year": a["formed_year"],
            "images": _artist_images(a["img_urls"]),
        },
        "has_mb": has_mb,
        "owned_count": sum(1 for r in albums if r["state"] == "local"),
        "albums": albums,
        "eps": eps,
        "extra": extra,
        "genres": artist_genres(artist_id),
    }


# ── Géneros ───────────────────────────────────────────────────────────────
# Índice en memoria de proceso: se construye una vez (~0,2 s) y vale hasta
# reiniciar el contenedor, igual que el resto del mapa la base es :ro.
_GENRE_INDEX = None
_GENRE_LOCK = threading.Lock()


def _genre_index():
    global _GENRE_INDEX
    with _GENRE_LOCK:
        if _GENRE_INDEX is None:
            labels = {}
            albums_by_genre = defaultdict(Counter)
            tags_by_genre = defaultdict(set)
            artists = {}
            with get_musica_local_conn() as conn:
                for r in conn.execute("SELECT artist_id, genre FROM albums WHERE origen IN (?, ?)",
                                      (LOCAL, OLD_LOCAL)):
                    for g in split_genres(r["genre"]):
                        key = genre_key(g)
                        labels.setdefault(key, g)
                        albums_by_genre[key][r["artist_id"]] += 1
                for r in conn.execute("SELECT id, name, origen, tags, img_urls FROM artists WHERE name IS NOT NULL"):
                    artists[r["id"]] = {"name": r["name"], "state": _state(r["origen"]),
                                        "images": _artist_images(r["img_urls"])}
                    for g in split_genres(r["tags"]):
                        key = genre_key(g)
                        labels.setdefault(key, g)
                        tags_by_genre[key].add(r["id"])
            _GENRE_INDEX = {"labels": labels, "albums": albums_by_genre,
                            "tags": tags_by_genre, "artists": artists}
        return _GENRE_INDEX


def artist_genres(artist_id):
    """Géneros de los discos del artista con cuántos discos tiene en cada uno;
    si sus discos no tienen género, sus tags (con 0 discos)."""
    index = _genre_index()
    counts = Counter()
    with get_musica_local_conn() as conn:
        for r in conn.execute("SELECT genre FROM albums WHERE artist_id = ? AND origen IN (?, ?)",
                              (artist_id, LOCAL, OLD_LOCAL)):
            for g in split_genres(r["genre"]):
                counts[genre_key(g)] += 1
        if not counts:
            row = conn.execute("SELECT tags FROM artists WHERE id = ?", (artist_id,)).fetchone()
            for g in split_genres(row["tags"] if row else ""):
                counts.setdefault(genre_key(g), 0)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"key": key, "label": index["labels"].get(key, key), "count": n} for key, n in ordered]


def genre_artists(key, exclude_artist_id=None, offset=0, limit=12):
    """Artistas de un género: primero por nº de discos propios de ese género,
    luego los que solo lo tienen como tag."""
    index = _genre_index()
    key = genre_key(key)
    album_counts = index["albums"].get(key, Counter())
    rows = []
    for artist_id in set(album_counts) | index["tags"].get(key, set()):
        if artist_id == exclude_artist_id or artist_id not in index["artists"]:
            continue
        rows.append(dict(index["artists"][artist_id], id=artist_id, count=album_counts.get(artist_id, 0)))
    rows.sort(key=lambda r: (-r["count"], r["name"].lower()))
    return {"key": key, "label": index["labels"].get(key, key), "total": len(rows),
            "offset": offset, "artists": rows[offset:offset + limit]}
