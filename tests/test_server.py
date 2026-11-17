def test_health(client):
    assert client.get("/health").get_json() == {"ok": True}


def test_index_and_shared_theme_files(client):
    assert b"Mapa de Discos" in client.get("/").data
    assert client.get("/theme-picker.js").status_code == 200
    assert client.get("/theme-palettes.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_api_artist(client):
    data = client.get("/api/artist/1").get_json()
    assert data["artist"]["name"] == "Radiohead"
    assert client.get("/api/artist/999").status_code == 404


def test_api_genre(client):
    data = client.get("/api/genre?key=alternative%20rock&exclude=1").get_json()
    assert [a["name"] for a in data["artists"]] == ["PJ Harvey"]
    assert client.get("/api/genre").status_code == 400
    # Parámetros raros no rompen
    assert client.get("/api/genre?key=rock&offset=x&limit=9999").status_code == 200


def test_api_search(client):
    assert client.get("/api/search?q=pj").get_json()[0]["label"] == "PJ Harvey"
