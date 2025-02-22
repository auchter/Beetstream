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
        rows = tx.query("SELECT DISTINCT albumartist, COUNT(*) FROM albums GROUP BY albumartist")

    def row_to_artist(row):
        return {
            'name': row[0],
            'id': artist_name_to_id(row[0]),
            'coverArt': '',
            'albumCount': row[1]
        }

    all_artists = [row_to_artist(row) for row in rows]
    all_artists.sort(key=lambda artist: strip_accents(artist['name']).upper())
    all_artists = filter(lambda artist: len(artist['name']) > 0, all_artists)

    indicies_dict = {}

    for artist in all_artists:
        index = strip_accents(artist['name'][0]).upper()
        if index not in indicies_dict:
            indicies_dict[index] = []
        indicies_dict[index].append(artist)

    indicies = []
    for index, artist in indicies_dict.items():
        indicies.append({
            "name": index,
            "artist": artist,
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
    albums = list(map(map_album, albums))

    return subsonic_response(request, {
        'artist': {
            Attr('id'): artist_id,
            Attr('name'): artist_name,
            Attr('albumCount'): len(albums),
            'album': albums,
        }
    })

@app.route('/rest/getArtistInfo2', methods=["GET", "POST"])
@app.route('/rest/getArtistInfo2.view', methods=["GET", "POST"])
def artistInfo2():
    artist_name = artist_id_to_name(request.values.get('id'))

    albums = g.lib.albums(artist_name.replace("'", "\\'"))
    albums = filter(lambda album: album.albumartist == artist_name, albums)
    mbid_list = sorted([album.mb_albumartistid for album in albums])
    mbid_counts = {item: mbid_list.count(item) for item in mbid_list}

    mbid = sorted(mbid_counts, key=lambda k: mbid_counts[k])[-1]

    return subsonic_response(request, {
        Elem('artistInfo2'): {
            Elem("biography"): f"wow. much artist. very {artist_name}, {mbid}",
            Elem("musicBrainzId"): mbid,
            Elem("lastFmUrl"): "",
            Elem("smallImageUrl"): "",
            Elem("mediumImageUrl"): "",
            Elem("largeImageUrl"): "",
        }
    })
