from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
from flask import g, request, Response
import mimetypes
from beets.random import random_objs

@app.route('/rest/getSong', methods=["GET", "POST"])
@app.route('/rest/getSong.view', methods=["GET", "POST"])
def song():
    id = int(song_subid_to_beetid(request.values.get('id')))
    song = g.lib.get_item(id)

    return subsonic_response(request, {
        "song": map_song(song)
    })

@app.route('/rest/getSongsByGenre', methods=["GET", "POST"])
@app.route('/rest/getSongsByGenre.view', methods=["GET", "POST"])
def songs_by_genre():
    genre = request.values.get('genre')
    count = int(request.values.get('count') or 10)
    offset = int(request.values.get('offset') or 0)

    songs = handleSizeAndOffset(list(g.lib.items('genre:' + genre.replace("'", "\\'"))), count, offset)

    return subsonic_response(request, {
        "songsByGenre": {
            "song": list(map(map_song, songs))
        }
    })

@app.route('/rest/stream', methods=["GET", "POST"])
@app.route('/rest/stream.view', methods=["GET", "POST"])
def stream_song():
    maxBitrate = int(request.values.get('maxBitRate') or 0) # TODO
    format = request.values.get('format') #TODO
    return stream(maxBitrate)

@app.route('/rest/download', methods=["GET", "POST"])
@app.route('/rest/download.view', methods=["GET", "POST"])
def download_song():
    return stream(0)

def stream(maxBitrate):
    id = int(song_subid_to_beetid(request.values.get('id')))
    item = g.lib.get_item(id)

    def generate():
        with open(item.path, "rb") as songFile:
            data = songFile.read(1024)
            while data:
                yield data
                data = songFile.read(1024)
    return Response(generate(), mimetype=mimetypes.guess_type(item.path.decode('utf-8'))[0])

@app.route('/rest/getRandomSongs', methods=["GET", "POST"])
@app.route('/rest/getRandomSongs.view', methods=["GET", "POST"])
def random_songs():
    size = int(request.values.get('size') or 10)
    songs = list(g.lib.items())
    songs = random_objs(songs, -1, size)

    return subsonic_response(request, {
        "randomSongs": {
            "song": list(map(map_song, songs))
        }
    })

# TODO link with Last.fm or ListenBrainz
@app.route('/rest/getTopSongs', methods=["GET", "POST"])
@app.route('/rest/getTopSongs.view', methods=["GET", "POST"])
def top_songs():
    return subsonic_response(request, {
        "topSongs": {}
    })

@app.route('/rest/getStarred', methods=["GET", "POST"])
@app.route('/rest/getStarred.view', methods=["GET", "POST"])
def starred_songs():
    return subsonic_response(request, {
        "starred": {
            "song": []
        }
    })

@app.route('/rest/getStarred2', methods=["GET", "POST"])
@app.route('/rest/getStarred2.view', methods=["GET", "POST"])
def starred2_songs():
    return subsonic_response(request, {
        "starred2": {
            "song": []
        }
    })
