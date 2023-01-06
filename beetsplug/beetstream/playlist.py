from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
from beets import library
from flask import request, g
import base64
from pathlib import Path
from beetsplug.beetstream import PLAYLIST_ID_PREFIX
import beets


class FileCache:
    def __init__(self, ctr):
        self.ctr_ = ctr
        self.dict_ = {}

    def get(self, path):
        path = Path(path)
        mtime = path.stat().st_mtime

        if path in self.dict_:
            stored_mtime, obj = self.dict_[path]
            if stored_mtime == mtime:
                return obj

        obj = self.ctr_(path)
        self.dict_[path] = (mtime, obj)
        return obj


class Playlist:
    def __init__(self, path):
        self.path_ = Path(path)
        self.ctime_ = self.path_.stat().st_ctime
        self.songs_ = []

        musicdir = Path(beets.config['directory'].get(str))

        paths = self.path_.read_text().split('\n')
        for path in paths:
            if path == '':
                continue

            path = Path(path)
            if not path.is_absolute():
                path = musicdir / path

            query = library.PathQuery('path', path)
            item = g.lib.items(query).get()
            if item:
                self.songs_.append(item)

    def get_songs(self):
        return self.songs_

    def get_song_count(self):
        return len(self.get_songs())

    def get_duration(self):
        return ceil(sum([x.length for x in self.get_songs()]))

    def get_created(self):
        return self.ctime_

    def get_name(self):
        return self.path_.stem

PLAYLIST_CACHE = FileCache(Playlist)

def pl_path_to_id(playlist_dir, playlist):
    rel = str(playlist.relative_to(playlist_dir))
    b64 = base64.b64encode(rel.encode('utf-8')).decode('utf-8')
    return f"{PLAYLIST_ID_PREFIX}{b64}"

def pl_id_to_path(playlist_dir, plid):
    plid = plid[len(PLAYLIST_ID_PREFIX):]
    rel = base64.b64decode(plid.encode('utf-8')).decode('utf-8')
    return playlist_dir / rel

@app.route('/rest/getPlaylists', methods=["GET", "POST"])
@app.route('/rest/getPlaylists.view', methods=["GET", "POST"])
def playlists():
    playlists = []
    pldir = Path(app.config['config']['playlist_dir'].get(str))
    for m3u in pldir.glob("**/*.m3u"):
        pl = PLAYLIST_CACHE.get(m3u)
        plid = pl_path_to_id(pldir, m3u)
        playlists.append({
            "id": pl_path_to_id(pldir, m3u),
            "name": pl.get_name(),
            "comment": "",
            "owner": "admin",
            "public": True,
            "songCount": pl.get_song_count(),
            "duration": pl.get_duration(),
            "created": timestamp_to_iso(pl.get_created()),
            "coverArt": 'playlist', # TODO: generate cover art?
        })

    return subsonic_response(request, {
        "playlists": {
            "playlist": playlists
        }
    })

@app.route('/rest/getPlaylist', methods=["GET", "POST"])
@app.route('/rest/getPlaylist.view', methods=["GET", "POST"])
def playlist():
    plid = request.values.get('id')
    pldir = Path(app.config['config']['playlist_dir'].get(str))
    plpath = pl_id_to_path(pldir, plid)
    pl = PLAYLIST_CACHE.get(plpath)

    return subsonic_response(request, {
        "playlist": {
            Attr("id"): plid,
            Attr("name"): pl.get_name(),
            Attr("comment"): "",
            Attr("owner"): "admin",
            Attr("public"): True,
            Attr("songCount"): pl.get_song_count(),
            Attr("duration"): pl.get_duration(),
            Attr("created"): timestamp_to_iso(pl.get_created()),
            Attr("coverArt"): "playlist",
            "entry": list(map(map_song, pl.get_songs())),
        }
    })
