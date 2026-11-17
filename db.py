import os
import sqlite3

MUSICA_LOCAL_DB = os.environ.get("MUSICA_LOCAL_DB", "/musica_local.sqlite")


def get_musica_local_conn() -> sqlite3.Connection:
    # immutable=1 -- se monta :ro en Docker; mode=ro solo no basta ahí
    # (mismo problema ya documentado en services/lastfm_explorer/db.py).
    conn = sqlite3.connect(f"file:{MUSICA_LOCAL_DB}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
