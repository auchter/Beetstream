from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
from flask import g, request, Response
import mimetypes
from beets.random import random_objs
import time
import datetime
import pylast
import pylistenbrainz

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

def do_scrobble(config, item, timestamp, submission):
    endpoints = {
        'last.fm': do_scrobble_lastfm,
        'listenbrainz': do_scrobble_listenbrainz,
        'log': do_scrobble_log,
    }

    for k, func in endpoints.items():
        if k in config:
            func(config[k], item, timestamp, submission)


def do_scrobble_listenbrainz(config, item, timestamp, submission):
    listen = pylistenbrainz.Listen(
        track_name=item.title,
        artist_name=item.artist,
        release_name=item.album,
        recording_mbid=item.mb_trackid,
        artist_mbids=[item.mb_artistid],
        release_mbid=item.mb_albumid,
        release_group_mbid=item.mb_releasegroupid,
        work_mbids=[item.mb_workid],
        tracknumber=item.track,
        listening_from='beetstream')

    client = pylistenbrainz.client.ListenBrainz()
    client.set_auth_token(config['user_token'].get(str))
    try:
        if submission:
            listen.listened_at = int(timestamp)
            client.submit_single_listen(listen)
        else:
            client.submit_playing_now(listen)
    except pylistenbrainz.errors.ListenBrainzAPIException as e:
        app.logger.error("listenbrainz error: " + str(e.message))


def do_scrobble_lastfm(config, item, timestamp, submission):
    lfm = pylast.LastFMNetwork(
            api_key=config['api_key'].get(str),
            api_secret=config['api_secret'].get(str),
            username=config['username'].get(str),
            password_hash=pylast.md5(config['password'].get(str)))

    if submission:
        lfm.scrobble(
            artist=item.artist,
            title=item.title,
            timestamp=timestamp,
            album=item.album,
            album_artist=item.albumartist,
            duration=item.length,
            track_number=item.track,
            mbid=item.mb_trackid)
    else:
        lfm.update_now_playing(
            artist=item.artist,
            title=item.title,
            album=item.album,
            album_artist=item.albumartist,
            duration=item.length,
            track_number=item.track,
            mbid=item.mb_trackid)


def do_scrobble_log(config, item, timestamp, submission):
    if not submission:
        return

    user = request.values.get('u')
    app.logger.info(f"{user} listened to {item.artist} - {item.album} - {item.title}")


@app.route('/rest/scrobble', methods=["GET", "POST"])
@app.route('/rest/scrobble.view', methods=["GET", "POST"])
def scrobble():
    user = request.values.get('u')
    user_config = app.config['config']['users'][user]
    if 'scrobble' not in user_config:
        return subsonic_response(request, {})

    ids = [int(song_subid_to_beetid(id)) for id in request.values.getlist('id')]
    times = [int(time) for t in request.values.getlist('time')]
    submission = True if request.values.get('submission', 'true') == 'true' else False

    # if you specify one time, better specify them all
    if len(times) > 0:
        assert(len(times) == len(ids))
    else:
        now = int(time.mktime(datetime.datetime.now().timetuple()))
        times = [now for _ in ids]

    for id, timestamp in zip(ids, times):
        item = g.lib.get_item(id)
        do_scrobble(user_config['scrobble'], item, timestamp, submission)

    return subsonic_response(request, {})

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
