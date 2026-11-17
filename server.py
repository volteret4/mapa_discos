#!/usr/bin/env python3
import os
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

import discografia

BASE_DIR = Path(__file__).parent

app = Flask(__name__)


def _int_or(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/search")
def api_search():
    return jsonify(discografia.search(request.args.get("q", "")))


@app.route("/api/artist/<int:artist_id>")
def api_artist(artist_id):
    data = discografia.artist(artist_id)
    if data is None:
        abort(404)
    return jsonify(data)


@app.route("/api/genre")
def api_genre():
    key = request.args.get("key", "")
    if not key.strip():
        abort(400)
    return jsonify(discografia.genre_artists(
        key,
        exclude_artist_id=_int_or(request.args.get("exclude"), None),
        offset=max(0, _int_or(request.args.get("offset"), 0)),
        limit=min(50, max(1, _int_or(request.args.get("limit"), 12))),
    ))


# Mismo contrato compartido que el resto de apps tumtumpa
@app.route("/theme-palettes.css")
def theme_palettes():
    return send_from_directory(BASE_DIR / "static", "theme-palettes.css")


@app.route("/theme-picker.js")
def theme_picker():
    return send_from_directory(BASE_DIR / "static", "theme-picker.js")


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
