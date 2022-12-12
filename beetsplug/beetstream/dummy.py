from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
from flask import request

# Fake endpoint to avoid some apps errors
@app.route('/rest/scrobble', methods=["GET", "POST"])
@app.route('/rest/scrobble.view', methods=["GET", "POST"])
@app.route('/rest/ping', methods=["GET", "POST"])
@app.route('/rest/ping.view', methods=["GET", "POST"])
def ping():
    return subsonic_response(request, {})

@app.route('/rest/getLicense', methods=["GET", "POST"])
@app.route('/rest/getLicense.view', methods=["GET", "POST"])
def getLicense():
    return subsonic_response(request, {
        "license": {
            "valid": True,
            "email": "foo@example.com",
            "trialExpires": "3000-01-01T00:00:00.000Z"
        }
    })

# TODO link with https://beets.readthedocs.io/en/stable/plugins/playlist.html
@app.route('/rest/getPlaylists', methods=["GET", "POST"])
@app.route('/rest/getPlaylists.view', methods=["GET", "POST"])
def playlists():
    return subsonic_response(request, {
        "playlists": {
            "playlist": []
        }
    })

@app.route('/rest/getMusicFolders', methods=["GET", "POST"])
@app.route('/rest/getMusicFolders.view', methods=["GET", "POST"])
def music_folder():
    return subsonic_response(request, {
        "musicFolders": {
            "musicFolder": [{
                "id": 0,
                "name": "Music",
            }]
        }
    })
