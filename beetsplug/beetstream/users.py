from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
from flask import g, request

@app.route('/rest/getUser', methods=["GET", "POST"])
@app.route('/rest/getUser.view', methods=["GET", "POST"])
def user():
    username = request.values.get('username')
    config = app.config['config']['users'][username]

    scrobble = False
    if 'scrobble' in config:
        scrobble = config['scrobble'].get(bool)

    return subsonic_response(request, {
        "user": {
            "username" : username,
            "email" : "foo@example.com",
            "scrobblingEnabled" : scrobble,
            "adminRole" : True,
            "settingsRole" : True,
            "downloadRole" : True,
            "uploadRole" : False,
            "playlistRole" : False,
            "coverArtRole" : True,
            "commentRole" : False,
            "podcastRole" : False,
            "streamRole" : True,
            "jukeboxRole" : False,
            "shareRole" : False,
            "videoConversionRole" : False,
            "avatarLastChanged" : "1970-01-01T00:00:00.000Z",
            "folder" : [ 0 ]
        }
    })
