from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
from flask import g, request
from beets.dbcore.query import (
    AndQuery,
    MatchQuery,
)

@app.route('/rest/search2', methods=["GET", "POST"])
@app.route('/rest/search2.view', methods=["GET", "POST"])
def search2():
    return search(2)

@app.route('/rest/search3', methods=["GET", "POST"])
@app.route('/rest/search3.view', methods=["GET", "POST"])
def search3():
    return search(3)

def search(version):
    query = request.values.get('query') or ""
    artistCount = int(request.values.get('artistCount') or 20)
    artistOffset = int(request.values.get('artistOffset') or 0)
    albumCount = int(request.values.get('albumCount') or 20)
    albumOffset = int(request.values.get('albumOffset') or 0)
    songCount = int(request.values.get('songCount') or 20)
    songOffset = int(request.values.get('songOffset') or 0)

    songs = handleSizeAndOffset(list(g.lib.items("title:{}".format(query.replace("'", "\\'")))), songCount, songOffset)
    albums = handleSizeAndOffset(list(g.lib.albums("album:{}".format(query.replace("'", "\\'")))), albumCount, albumOffset)

    with g.lib.transaction() as tx:
        rows = tx.query("SELECT DISTINCT albumartist FROM albums")
    artists = [row[0] for row in rows]
    artists = list(filter(lambda artist: strip_accents(query).lower() in strip_accents(artist).lower(), artists))
    artists.sort(key=lambda name: strip_accents(name).upper())
    artists = handleSizeAndOffset(artists, artistCount, artistOffset)

    return subsonic_response(request, {
        "searchResult{}".format(version): {
            "artist": list(map(map_artist, artists)),
            "album": list(map(map_album, albums)),
            "song": list(map(map_song, songs))
        }
    })

@app.route('/rest/getLyrics', methods=["GET", "POST"])
@app.route('/rest/getLyrics.view', methods=["GET", "POST"])
def getLyrics():
    artist = request.values.get("artist") or ""
    title = request.values.get("title") or ""

    query = AndQuery([
        MatchQuery("artist", artist),
        MatchQuery("title", title),
    ])
    items = g.lib.items(query=query)

    if len(items) > 0:
        item = items[0]

    return subsonic_response(request, {
        "lyrics": {
            Attr("artist"): item.artist,
            Attr("title"): item.title,
            ElemText("value"): item.lyrics,
        }
    })

