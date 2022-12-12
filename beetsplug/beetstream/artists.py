import time
from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
from flask import g, request

@app.route('/rest/getArtists', methods=["GET", "POST"])
@app.route('/rest/getArtists.view', methods=["GET", "POST"])
def all_artists():
    return get_artists("artists")

@app.route('/rest/getIndexes', methods=["GET", "POST"])
@app.route('/rest/getIndexes.view', methods=["GET", "POST"])
def indexes():
    return get_artists("indexes")

def get_artists(version):
    with g.lib.transaction() as tx:
        rows = tx.query("SELECT DISTINCT albumartist FROM albums")
    all_artists = [row[0] for row in rows]
    all_artists.sort(key=lambda name: strip_accents(name).upper())
    all_artists = filter(lambda name: len(name) > 0, all_artists)

    indicies_dict = {}

    for name in all_artists:
        index = strip_accents(name[0]).upper()
        if index not in indicies_dict:
            indicies_dict[index] = []
        indicies_dict[index].append(name)

    indicies = []
    for index, artist_names in indicies_dict.items():
        indicies.append({
            "name": index,
            "artist": list(map(map_artist, artist_names))
        })

    return subsonic_response(request, {
        version: {
            "ignoredArticles": "",
            "lastModified": int(time.time() * 1000),
            "index": indicies
        }
    })

@app.route('/rest/getArtist', methods=["GET", "POST"])
@app.route('/rest/getArtist.view', methods=["GET", "POST"])
def artist():
    artist_id = request.values.get('id')
    artist_name = artist_id_to_name(artist_id)
    albums = g.lib.albums(artist_name.replace("'", "\\'"))
    albums = filter(lambda album: album.albumartist == artist_name, albums)

    return subsonic_response(request, {
        'artist': {
            'id': artist_id,
            'artist_name': artist_name,
            'album': list(map(map_album, albums)),
        }
    })

@app.route('/rest/getArtistInfo2', methods=["GET", "POST"])
@app.route('/rest/getArtistInfo2.view', methods=["GET", "POST"])
def artistInfo2():
    artist_name = artist_id_to_name(request.values.get('id'))

    return subsonic_response(request, {
        'artistInfo2': {
            "biography": f"wow. much artist. very {artist_name}",
            "musicBrainzId": "",
            "lastFmUrl": "",
            "smallImageUrl": "",
            "mediumImageUrl": "",
            "largeImageUrl": "",
        }
    })
