# mapa_discos

## Arquitectura

- `db.py` — `get_musica_local_conn()`: `mode=ro` + `immutable=1`, porque la
  base llega montada en solo lectura.
- `normalize.py` — `normalize_title` (minúsculas, sin acentos, sin "The",
  sin puntuación ni sufijos "(Deluxe Edition)"/"Remaster"...) para cruzar
  títulos de MusicBrainz con `albums.name`; `genre_key`/`split_genres` para
  que "Post-Rock" y "post rock" sean el mismo género.
- `discografia.py` — consultas:
  - `artist(id)`: álbumes originales + EPs desde `musicbrainz_discography`,
    cruzados con `albums` (origen `local` / `antiguo_local`). Emparejado: por
    `musicbrainz_discography.album_id`, luego título normalizado exacto,
    luego prefijo (≥ 6 caracteres). Los discos propios que no casan con
    ningún release-group (de ningún tipo) van a `extra` ("Otros tuyos").
    Artistas sin filas en `musicbrainz_discography` (~40 %): solo sus
    discos propios, `has_mb: false`.
  - `artist_genres(id)`: tokens de `albums.genre` de sus discos; si no hay,
    `artists.tags`.
  - `genre_artists(key)`: índice en memoria de proceso (`_GENRE_INDEX`,
    ~0,2 s la primera vez) género -> artistas por nº de discos propios, más
    los que solo lo tienen como tag (count 0).
  - `search(q)`: artistas, discos propios y títulos Album/EP de MusicBrainz.
- `server.py` — Flask: `/api/search`, `/api/artist/<id>`, `/api/genre`,
  `/health`, `/` (templates/index.html) y los archivos de tema compartidos.
- `static/app.js` — grafo con Cytoscape.js (cdnjs). Cada nodo creado al
  desplegar otro guarda `data.owner`; plegar borra recursivamente lo que
  creó. Artistas (`ar:<id>`) y géneros (`ge:<key>`) son únicos: si ya están
  en el mapa solo se añade la flecha. La colocación es manual (abanico
  hacia fuera, eligiendo la orientación que menos choca con lo ya
  dibujado) para que el mapa no se reordene entero al desplegar; el botón
  "Reordenar" lanza `cose` si se enmaraña.
- `static/theme-palettes.css` / `static/theme-picker.js` — tema compartido
  con el resto de módulos de REPEAT-ONE; mantenerlos idénticos a los suyos.
- `herramientas/crear_musica_local.py` — crea las tres tablas desde una carpeta
  de música (+ MusicBrainz) para quien no tenga music-fuzzy.

## Por qué las portadas vienen de Cover Art Archive

`albums.album_art_path` suele apuntar a rutas de otro equipo y no se puede
servir; además así hay portada también para los discos que faltan. Se prueba primero la del release-group y luego la del release
propio (`albums.mbid`): Cover Art Archive no tiene todas las ediciones y a
veces devuelve 404/500. La web prueba cada URL con `new Image()` y se queda
con la primera que carga.

## Pestaña de music-fuzzy

`?embed=mfuz` activa el doble clic / botón "Abrir en Music Browser", que
hace `console.info("mfuz://open?artist=…&album=…")`. No se usa navegación a
`mfuz://` porque QtWebEngine no la pasa a `acceptNavigationRequest` sin
registrar el esquema antes de crear la QApplication (y eso vive en
`main.py` de music-fuzzy, no en el módulo).
