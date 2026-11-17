# mapa_discos

Mapa conceptual de discografías sobre `musica_local.sqlite` (la base de
music-fuzzy). Buscas un artista o un disco y aparece como un grafo:

```
           [Géneros] ──▶ Art Rock ──▶ PJ Harvey ──▶ sus álbumes…
               ▲
(Pablo Honey) ◀── RADIOHEAD ──▶ (Kid A ✓)
               │        └────▶ [EPs] ──▶ EPs…
               ▼
         (OK Computer ✓)
```

- De entrada, solo los **álbumes originales** del artista (Album sin
  directos, recopilatorios, remixes, BSO… — mismo criterio que
  `discografia-gaps`), marcando los que tienes (borde verde), los que
  tuviste (`antiguo_local`, borde discontinuo) y los que te faltan (apagados).
- **EPs**, **Géneros** y **Otros tuyos** (discos tuyos sin ficha en
  MusicBrainz) se despliegan con un clic y se pliegan con otro.
- Clic en un **género**: otros artistas de tu colección con ese género,
  ordenados por cuántos discos suyos tienes de él. Clic en uno de ellos:
  su discografía, y así sucesivamente.
- Portadas desde Cover Art Archive (también las de los discos que te
  faltan); fotos de artista desde `artists.img_urls`.

## Instalación

Necesitas Docker y una base `musica_local.sqlite` con tu colección.

```bash
git clone https://github.com/volteret4/mapa_discos.git && cd mapa_discos && cp .env.example .env && mkdir -p datos
```

### La base de tu colección

Si usas music-fuzzy, su `musica_local.sqlite` vale tal cual: pon su ruta en `MUSICA_LOCAL` dentro de `.env`.

Si no, créala a partir de tu carpeta de música (un disco por carpeta, con etiquetas de artista y álbum):

```bash
pip install mutagen requests && python3 herramientas/crear_musica_local.py /ruta/a/tu/musica datos/musica_local.sqlite --musicbrainz
```

Con `--musicbrainz` baja también la discografía de cada artista, para ver los discos que te faltan. MusicBrainz admite una consulta por segundo: cuenta unos 2 segundos por artista. Sin esa opción solo salen tus discos. Vuelve a lanzarlo cuando añadas música: solo baja lo nuevo, y lo que ya no esté queda como «lo tuviste».

### Arrancar

```bash
docker compose up -d --build
```

Se abre en <http://localhost:8779>.

Sin Docker:

```bash
pip install -r requirements.txt && MUSICA_LOCAL_DB=datos/musica_local.sqlite PORT=8779 python3 server.py
```

### Qué tablas lee

| Tabla | Columnas |
|---|---|
| `artists` | `id`, `name`, `origen` (`local` o `antiguo_local`), `origin`, `formed_year`, `tags`, `img_urls` |
| `albums` | `id`, `artist_id`, `name`, `year`, `originalyear`, `genre`, `origen`, `mbid` |
| `musicbrainz_discography` | `artist_id`, `album_id`, `mbid` (release group), `title`, `release_type`, `first_release_date`, `secondary_types` |

Cualquier herramienta que rellene esas tablas sirve.

Es un módulo de [REPEAT-ONE](https://volteret4.github.io/repeat-one-web/) (puerto 8779), y funciona igual por separado. Hay una [demo con datos reales](https://volteret4.github.io/repeat-one-web/demo/mapa/).

## Integración con music-fuzzy

La pestaña "Flujo" de music-fuzzy (`modules/discografia_flow_module.py`)
carga esta web con `?embed=mfuz`. En ese modo, doble clic en un disco tuyo
(o el botón "Abrir en Music Browser") emite un mensaje de consola
`mfuz://open?artist=…&album=…` que la pestaña intercepta para lanzar la
búsqueda `a:Artista d:Disco` en Music Browser.

## Tests

```bash
python3 -m pytest tests
```
