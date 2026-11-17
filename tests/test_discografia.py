import discografia
from normalize import genre_key, normalize_title, split_genres


def test_normalize_title_ignores_edition_suffix_and_punctuation():
    assert normalize_title("OK Computer (Deluxe Edition)") == normalize_title("ok computer")
    assert normalize_title("The Bends") == normalize_title("Bends")


def test_genre_helpers():
    assert genre_key("Post-Rock") == genre_key("post rock") == "post rock"
    assert split_genres("Alternative Rock, Unknown; Art Rock") == ["Alternative Rock", "Art Rock"]


def test_artist_albums_are_originals_with_ownership(musica_local_path):
    data = discografia.artist(1)
    titles = [r["title"] for r in data["albums"]]
    # Sin el directo ni el single, en orden de publicación
    assert titles == ["Pablo Honey", "OK Computer", "Kid A", "Amnesiac"]
    states = {r["title"]: r["state"] for r in data["albums"]}
    assert states == {"Pablo Honey": None, "OK Computer": "local", "Kid A": "local", "Amnesiac": "antiguo"}
    assert data["owned_count"] == 2
    assert [r["title"] for r in data["eps"]] == ["My Iron Lung"]


def test_owned_album_without_mb_entry_goes_to_extra(musica_local_path):
    extra = discografia.artist(1)["extra"]
    assert [r["title"] for r in extra] == ["Live Recordings 1995"]


def test_covers_prefer_release_group_then_owned_release(musica_local_path):
    okc = next(r for r in discografia.artist(1)["albums"] if r["title"] == "OK Computer")
    assert okc["covers"] == [
        "https://coverartarchive.org/release-group/rg-okc/front-250",
        "https://coverartarchive.org/release/rel-okc/front-250",
    ]


def test_artist_images_spotify_first_and_both_formats(musica_local_path):
    assert discografia.artist(1)["artist"]["images"][0].startswith("https://i.scdn.co/")
    assert discografia.artist(2)["artist"]["images"] == ["https://i.scdn.co/image/pj"]


def test_artist_without_mb_shows_own_albums(musica_local_path):
    data = discografia.artist(4)
    assert data["has_mb"] is False
    assert [(r["title"], r["year"], r["state"]) for r in data["albums"]] == [("Disco Suelto", "2010", "local")]


def test_unknown_artist(musica_local_path):
    assert discografia.artist(999) is None


def test_artist_genres_count_albums(musica_local_path):
    genres = {g["key"]: g["count"] for g in discografia.artist_genres(1)}
    # "alternative-rock" de Amnesiac cuenta igual que "Alternative Rock"
    assert genres == {"alternative rock": 3, "art rock": 1}


def test_artist_genres_fall_back_to_tags(musica_local_path):
    assert discografia.artist_genres(4) == [{"key": "rock", "label": "Rock", "count": 1}]


def test_genre_artists_ordered_and_excluding(musica_local_path):
    page = discografia.genre_artists("Art Rock", exclude_artist_id=None)
    assert [(a["name"], a["count"]) for a in page["artists"]] == [
        ("Gente Que Ya No Está", 1), ("Radiohead", 1)]
    page = discografia.genre_artists("alternative rock", exclude_artist_id=1)
    assert [a["name"] for a in page["artists"]] == ["PJ Harvey"]
    assert page["artists"][0]["state"] == "local"


def test_genre_artists_paging(musica_local_path):
    page = discografia.genre_artists("rock", offset=1, limit=1)
    assert page["total"] == 3 and page["offset"] == 1 and len(page["artists"]) == 1


def test_search_artists_and_albums(musica_local_path):
    results = discografia.search("kid")
    assert results[0]["label"] == "Kid A" and results[0]["type"] == "album"
    # El título de MusicBrainz del mismo disco no sale repetido
    assert sum(1 for r in results if r["label"] == "Kid A") == 1
    assert discografia.search("radio")[0] == {
        "type": "artist", "artist_id": 1, "label": "Radiohead", "state": "local"}
    assert discografia.search("k") == []
