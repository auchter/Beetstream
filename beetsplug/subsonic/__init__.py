# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""A Web interface to beets."""
from beets.plugins import BeetsPlugin
from beets import ui
from beets import util
import beets.library
import flask
from flask import g, jsonify, request, send_from_directory, Response
from werkzeug.routing import BaseConverter, PathConverter
import os
from unidecode import unidecode
import json
import base64
from datetime import datetime
import unicodedata
import mimetypes
from beets.random import random_objs
import time
import xml.etree.cElementTree as ET
from math import ceil
from flask_cors import CORS
from PIL import Image
import io
from xml.dom import minidom

ARTIST_ID_PREFIX = "1"
ALBUM_ID_PREFIX = "2"
SONG_ID_PREFIX = "3"

# Utilities.

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def timestamp_to_iso(timestamp):
    return datetime.fromtimestamp(int(timestamp)).isoformat()

def is_json(res_format):
    return res_format == 'json' or res_format == 'jsonp'

def wrap_res(key, json):
    return {
        "subsonic-response": {
            "status": "ok",
            "version": "1.16.1",
            key: json
        }
    }

def jsonpify(request, data):
    if request.values.get("f") == "jsonp":
        callback = request.values.get("callback")
        return f"{callback}({json.dumps(data)});"
    else:
        return flask.jsonify(data)

def get_xml_root():
    root = ET.Element('subsonic-response')
    root.set('xmlns', 'http://subsonic.org/restapi')
    root.set('status', 'ok')
    root.set('version', '1.16.1')
    return root

def xml_to_string(xml):
    # Add declaration: <?xml version="1.0" encoding="UTF-8"?>
    return minidom.parseString(ET.tostring(xml, encoding='unicode', method='xml', xml_declaration=True)).toprettyxml()

def map_album(album):
    album = dict(album)
    return {
        "id": album_beetid_to_subid(str(album["id"])),
        "name": album["album"],
        "title": album["album"],
        "album": album["album"],
        "artist": album["albumartist"],
        "artistId": artist_name_to_id(album["albumartist"]),
        "parent": artist_name_to_id(album["albumartist"]),
        "isDir": True,
        "coverArt": album_beetid_to_subid(str(album["id"])) or "",
        "songCount": 1, # TODO
        "duration": 1, # TODO
        "playCount": 1, # TODO
        "created": timestamp_to_iso(album["added"]),
        "year": album["year"],
        "genre": album["genre"],
        "starred": "1970-01-01T00:00:00.000Z", # TODO
        "averageRating": 0 # TODO
    }

def map_album_xml(xml, album):
    album = dict(album)
    xml.set("id", album_beetid_to_subid(str(album["id"])))
    xml.set("name", album["album"])
    xml.set("title", album["album"])
    xml.set("album", album["album"])
    xml.set("artist", album["albumartist"])
    xml.set("artistId", artist_name_to_id(album["albumartist"]))
    xml.set("parent", artist_name_to_id(album["albumartist"]))
    xml.set("isDir", "true")
    xml.set("coverArt", album_beetid_to_subid(str(album["id"])) or "")
    xml.set("songCount", str(1)) # TODO
    xml.set("duration", str(1)) # TODO
    xml.set("playCount", str(1)) # TODO
    xml.set("created", timestamp_to_iso(album["added"]))
    xml.set("year", str(album["year"]))
    xml.set("genre", album["genre"])
    xml.set("starred", "1970-01-01T00:00:00.000Z") # TODO
    xml.set("averageRating", "0") # TODO

def map_album_list(album):
    album = dict(album)
    return {
        "id": album_beetid_to_subid(str(album["id"])),
        "parent": artist_name_to_id(album["albumartist"]),
        "isDir": True,
        "title": album["album"],
        "album": album["album"],
        "artist": album["albumartist"],
        "year": album["year"],
        "genre": album["genre"],
        "coverArt": album_beetid_to_subid(str(album["id"])) or "",
        "userRating": 5, # TODO
        "averageRating": 5, # TODO
        "playCount": 1,  # TODO
        "created": timestamp_to_iso(album["added"]),
        "starred": ""
    }

def map_album_list_xml(xml, album):
    album = dict(album)
    xml.set("id", album_beetid_to_subid(str(album["id"])))
    xml.set("parent", artist_name_to_id(album["albumartist"]))
    xml.set("isDir", "true")
    xml.set("title", album["album"])
    xml.set("album", album["album"])
    xml.set("artist", album["albumartist"])
    xml.set("year", str(album["year"]))
    xml.set("genre", album["genre"])
    xml.set("coverArt", album_beetid_to_subid(str(album["id"])) or "")
    xml.set("userRating", "5") # TODO
    xml.set("averageRating", "5") # TODO
    xml.set("playCount", "1")  # TODO
    xml.set("created", timestamp_to_iso(album["added"]))
    xml.set("starred", "")

def map_song(song):
    song = dict(song)
    return {
        "id": song_beetid_to_subid(str(song["id"])),
        "parent": album_beetid_to_subid(str(song["album_id"])),
        "isDir": False,
        "title": song["title"],
        "name": song["title"],
        "album": song["album"],
        "artist": song["albumartist"],
        "track": song["track"],
        "year": song["year"],
        "genre": song["genre"],
        "coverArt": album_beetid_to_subid(str(song["album_id"])) or "",
        # TODO "size": 3612800,
        "contentType": mimetypes.guess_type(song["path"].decode('utf-8'))[0],
        "suffix": song["format"].lower(),
        "duration": ceil(song["length"]),
        "bitRate": ceil(song["bitrate"]/1000),
        "path": song["path"].decode('utf-8'),
        "playCount": 1745, #TODO
        "created": timestamp_to_iso(song["added"]),
        # "starred": "2019-10-23T04:41:17.107Z",
        "albumId": album_beetid_to_subid(str(song["album_id"])),
        "artistId": artist_name_to_id(song["albumartist"]),
        "type": "music"
    }

def map_song_xml(xml, song):
    song = dict(song)
    xml.set("id", song_beetid_to_subid(str(song["id"])))
    xml.set("parent", album_beetid_to_subid(str(song["album_id"])))
    xml.set("isDir", "false")
    xml.set("title", song["title"])
    xml.set("name", song["title"])
    xml.set("album", song["album"])
    xml.set("artist", song["albumartist"])
    xml.set("track", str(song["track"]))
    xml.set("year", str(song["year"]))
    xml.set("genre", song["genre"])
    xml.set("coverArt", album_beetid_to_subid(str(song["album_id"])) or "")
    xml.set("contentType", mimetypes.guess_type(song["path"].decode('utf-8'))[0])
    xml.set("suffix", song["format"].lower())
    xml.set("duration", str(ceil(song["length"])))
    xml.set("bitRate", str(ceil(song["bitrate"]/1000)))
    xml.set("path", song["path"].decode('utf-8'))
    xml.set("playCount", str(1745)) #TODO
    xml.set("created", timestamp_to_iso(song["added"]))
    xml.set("albumId", album_beetid_to_subid(str(song["album_id"])))
    xml.set("artistId", artist_name_to_id(song["albumartist"]))
    xml.set("type", "music")

def map_artist(artist_name):
    return {
        "id": artist_name_to_id(artist_name),
        "name": artist_name,
        # TODO
        # "starred": "2021-07-03T06:15:28.757Z", # nothing if not starred
        "coverArt": "",
        "albumCount": 1,
        "artistImageUrl": "https://t4.ftcdn.net/jpg/00/64/67/63/360_F_64676383_LdbmhiNM6Ypzb3FM4PPuFP9rHe7ri8Ju.jpg"
    }

def map_artist_xml(xml, artist_name):
    xml.set("id", artist_name_to_id(artist_name))
    xml.set("name", artist_name)
    xml.set("coverArt", "")
    xml.set("albumCount", "1")
    xml.set("artistImageUrl", "https://t4.ftcdn.net/jpg/00/64/67/63/360_F_64676383_LdbmhiNM6Ypzb3FM4PPuFP9rHe7ri8Ju.jpg")

def artist_name_to_id(name):
    base64_name = base64.b64encode(name.encode('utf-8')).decode('utf-8')
    return f"{ARTIST_ID_PREFIX}{base64_name}"

def artist_id_to_name(id):
    base64_id = id[len(ARTIST_ID_PREFIX):]
    return base64.b64decode(base64_id.encode('utf-8')).decode('utf-8')

def album_beetid_to_subid(id):
    return f"{ALBUM_ID_PREFIX}{id}"

def album_subid_to_beetid(id):
    return id[len(ALBUM_ID_PREFIX):]

def song_beetid_to_subid(id):
    return f"{SONG_ID_PREFIX}{id}"

def song_subid_to_beetid(id):
    return id[len(SONG_ID_PREFIX):]

def handleSizeAndOffset(collection, size, offset):
    if size is not None:
        if offset is not None:
            return collection[offset:offset + size]
        else:
            return collection[0:size]
    else:
        return collection

def _rep(obj, expand=False):
    """Get a flat -- i.e., JSON-ish -- representation of a beets Item or
    Album object. For Albums, `expand` dictates whether tracks are
    included.
    """
    out = dict(obj)

    if isinstance(obj, beets.library.Item):
        if app.config.get('INCLUDE_PATHS', False):
            out['path'] = util.displayable_path(out['path'])
        else:
            del out['path']

        # Filter all bytes attributes and convert them to strings.
        for key, value in out.items():
            if isinstance(out[key], bytes):
                out[key] = base64.b64encode(value).decode('ascii')

        # Get the size (in bytes) of the backing file. This is useful
        # for the Tomahawk resolver API.
        try:
            out['size'] = os.path.getsize(util.syspath(obj.path))
        except OSError:
            out['size'] = 0

        return out

    elif isinstance(obj, beets.library.Album):
        del out['artpath']
        if expand:
            out['items'] = [_rep(item) for item in obj.items()]
        return out


def json_generator(items, root, expand=False):
    """Generator that dumps list of beets Items or Albums as JSON

    :param root:  root key for JSON
    :param items: list of :class:`Item` or :class:`Album` to dump
    :param expand: If true every :class:`Album` contains its items in the json
                   representation
    :returns:     generator that yields strings
    """
    yield '{"%s":[' % root
    first = True
    for item in items:
        if first:
            first = False
        else:
            yield ','
        yield json.dumps(_rep(item, expand=expand))
    yield ']}'


def is_expand():
    """Returns whether the current request is for an expanded response."""

    return flask.request.values.get('expand') is not None


def is_delete():
    """Returns whether the current delete request should remove the selected
    files.
    """

    return flask.request.values.get('delete') is not None


def get_method():
    """Returns the HTTP method of the current request."""
    return flask.request.method


def resource(name, patchable=False):
    """Decorates a function to handle RESTful HTTP requests for a resource.
    """
    def make_responder(retriever):
        def responder(ids):
            entities = [retriever(id) for id in ids]
            entities = [entity for entity in entities if entity]

            if get_method() == "DELETE":
                for entity in entities:
                    entity.remove(delete=is_delete())

                return flask.make_response(jsonify({'deleted': True}), 200)

            elif get_method() == "PATCH" and patchable:
                for entity in entities:
                    entity.update(flask.request.get_json())
                    entity.try_sync(True, False)  # write, don't move

                if len(entities) == 1:
                    return jsonpify(request, _rep(entities[0], expand=is_expand()))
                elif entities:
                    return app.response_class(
                        json_generator(entities, root=name),
                        mimetype='application/json'
                    )

            elif get_method() == "GET":
                if len(entities) == 1:
                    return jsonpify(request, _rep(entities[0], expand=is_expand()))
                elif entities:
                    return app.response_class(
                        json_generator(entities, root=name),
                        mimetype='application/json'
                    )
                else:
                    return flask.abort(404)

            else:
                return flask.abort(405)

        responder.__name__ = 'get_{0}'.format(name)

        return responder
    return make_responder


def resource_query(name, patchable=False):
    """Decorates a function to handle RESTful HTTP queries for resources.
    """
    def make_responder(query_func):
        def responder(queries):
            entities = query_func(queries)

            if get_method() == "DELETE":
                for entity in entities:
                    entity.remove(delete=is_delete())

                return flask.make_response(jsonify({'deleted': True}), 200)

            elif get_method() == "PATCH" and patchable:
                for entity in entities:
                    entity.update(flask.request.get_json())
                    entity.try_sync(True, False)  # write, don't move

                return app.response_class(
                    json_generator(entities, root=name),
                    mimetype='application/json'
                )

            elif get_method() == "GET":
                return app.response_class(
                    json_generator(
                        entities,
                        root='results', expand=is_expand()
                    ),
                    mimetype='application/json'
                )

            else:
                return flask.abort(405)

        responder.__name__ = 'query_{0}'.format(name)

        return responder

    return make_responder


def resource_list(name):
    """Decorates a function to handle RESTful HTTP request for a list of
    resources.
    """
    def make_responder(list_all):
        def responder():
            return app.response_class(
                json_generator(list_all(), root=name, expand=is_expand()),
                mimetype='application/json'
            )
        responder.__name__ = 'all_{0}'.format(name)
        return responder
    return make_responder


def _get_unique_table_field_values(model, field, sort_field):
    """ retrieve all unique values belonging to a key from a model """
    if field not in model.all_keys() or sort_field not in model.all_keys():
        raise KeyError
    with g.lib.transaction() as tx:
        rows = tx.query('SELECT DISTINCT "{0}" FROM "{1}" ORDER BY "{2}"'
                        .format(field, model._table, sort_field))
    return [row[0] for row in rows]


class IdListConverter(BaseConverter):
    """Converts comma separated lists of ids in urls to integer lists.
    """

    def to_python(self, value):
        ids = []
        for id in value.split(','):
            try:
                ids.append(int(id))
            except ValueError:
                pass
        return ids

    def to_url(self, value):
        return ','.join(str(v) for v in value)


class QueryConverter(PathConverter):
    """Converts slash separated lists of queries in the url to string list.
    """

    def to_python(self, value):
        queries = value.split('/')
        return [query.replace('\\', os.sep) for query in queries]

    def to_url(self, value):
        return ','.join([v.replace(os.sep, '\\') for v in value])


class EverythingConverter(PathConverter):
    regex = '.*?'


# Flask setup.

app = flask.Flask(__name__)
app.url_map.converters['idlist'] = IdListConverter
app.url_map.converters['query'] = QueryConverter
app.url_map.converters['everything'] = EverythingConverter


@app.before_request
def before_request():
    g.lib = app.config['lib']

# System

# Fake endpoint to avoid some apps errors
@app.route('/rest/scrobble', methods=["GET", "POST"])
@app.route('/rest/scrobble.view', methods=["GET", "POST"])
@app.route('/rest/ping', methods=["GET", "POST"])
@app.route('/rest/ping.view', methods=["GET", "POST"])
def ping():
    res_format = request.values.get('f') or 'xml'

    if (is_json(res_format)):
        return jsonpify(request, {
            "subsonic-response": {
                "status": "ok",
                "version": "1.16.1"
            }
        })
    else:
        root = get_xml_root()
        return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getLicense', methods=["GET", "POST"])
@app.route('/rest/getLicense.view', methods=["GET", "POST"])
def getLicense():
    res_format = request.values.get('f') or 'xml'

    if (is_json(res_format)):
        return jsonpify(request, wrap_res("license", {
            "valid": True,
            "email": "foo@example.com",
            "trialExpires": "3000-01-01T00:00:00.000Z"
        }))
    else:
        root = get_xml_root()
        l = ET.SubElement(root, 'license')
        l.set("valid", "true")
        l.set("email", "foo@example.com")
        l.set("trialExpires", "3000-01-01T00:00:00.000Z")
        return Response(xml_to_string(root), mimetype='text/xml')

# Files
@app.route('/rest/stream', methods=["GET", "POST"])
@app.route('/rest/stream.view', methods=["GET", "POST"])
def stream_song():
    id = int(song_subid_to_beetid(request.values.get('id')))
    maxBitrate = int(request.values.get('maxBitRate') or 0)
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
    res_format = request.values.get('f') or 'xml'
    size = int(request.values.get('size') or 10)
    songs = list(g.lib.items())
    songs = random_objs(songs, -1, size)

    if (is_json(res_format)):
        return jsonpify(request, wrap_res("randomSongs", {
            "song": list(map(map_song, songs))
        }))
    else:
        root = get_xml_root()
        album = ET.SubElement(root, 'randomSongs')

        for song in songs:
            s = ET.SubElement(album, 'song')
            map_song_xml(s, song)

        return Response(xml_to_string(root), mimetype='text/xml')


# TODO link with https://beets.readthedocs.io/en/stable/plugins/playlist.html
@app.route('/rest/getPlaylists', methods=["GET", "POST"])
@app.route('/rest/getPlaylists.view', methods=["GET", "POST"])
def playlists():
    res_format = request.values.get('f') or 'xml'
    if (is_json(res_format)):
        return jsonpify(request, wrap_res("playlists", {
            "playlist": []
        }))
    else:
        root = get_xml_root()
        ET.SubElement(root, 'playlists')
        return Response(xml_to_string(root), mimetype='text/xml')


# TODO link with Last.fm or ListenBrainz
@app.route('/rest/getTopSongs', methods=["GET", "POST"])
@app.route('/rest/getTopSongs.view', methods=["GET", "POST"])
def top_songs():
    res_format = request.values.get('f') or 'xml'
    if (is_json(res_format)):
        return jsonpify(request, wrap_res("topSongs", {}))
    else:
        root = get_xml_root()
        ET.SubElement(root, 'topSongs')
        return Response(xml_to_string(root), mimetype='text/xml')


@app.route('/rest/getStarred', methods=["GET", "POST"])
@app.route('/rest/getStarred.view', methods=["GET", "POST"])
def starred_songs():
    res_format = request.values.get('f') or 'xml'
    if (is_json(res_format)):
        return jsonpify(request, wrap_res("starred", {
            "song": []
        }))
    else:
        root = get_xml_root()
        ET.SubElement(root, 'starred')
        return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getStarred2', methods=["GET", "POST"])
@app.route('/rest/getStarred2.view', methods=["GET", "POST"])
def starred2_songs():
    res_format = request.values.get('f') or 'xml'
    if (is_json(res_format)):
        return jsonpify(request, wrap_res("starred2", {
            "song": []
        }))
    else:
        root = get_xml_root()
        ET.SubElement(root, 'starred2')
        return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/search2', methods=["GET", "POST"])
@app.route('/rest/search2.view', methods=["GET", "POST"])
def search2():
    return search(2)

@app.route('/rest/search3', methods=["GET", "POST"])
@app.route('/rest/search3.view', methods=["GET", "POST"])
def search3():
    return search(3)

def search(version):
    res_format = request.values.get('f') or 'xml'
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

    if (is_json(res_format)):
        return jsonpify(request, wrap_res("searchResult{}".format(version), {
            "artist": list(map(map_artist, artists)),
            "album": list(map(map_album, albums)),
            "song": list(map(map_song, songs))
        }))
    else:
        root = get_xml_root()
        search_result = ET.SubElement(root, 'searchResult{}'.format(version))

        for artist in artists:
            a = ET.SubElement(search_result, 'artist')
            map_artist_xml(a, artist)

        for album in albums:
            a = ET.SubElement(search_result, 'album')
            map_album_xml(a, album)

        for song in songs:
            s = ET.SubElement(search_result, 'song')
            map_song_xml(s, song)

        return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getMusicFolders', methods=["GET", "POST"])
@app.route('/rest/getMusicFolders.view', methods=["GET", "POST"])
def music_folder():
    res_format = request.values.get('f') or 'xml'
    if (is_json(res_format)):
        return jsonpify(request, wrap_res("musicFolders", {
            "musicFolder": [{
                "id": 0,
                "name": "Music"
            }]
        }))
    else:
        root = get_xml_root()
        folder = ET.SubElement(root, 'musicFolders')
        folder.set("id", "0")
        folder.set("name", "Music")

        return Response(xml_to_string(root), mimetype='text/xml')

# Albums
@app.route('/rest/getGenres', methods=["GET", "POST"])
@app.route('/rest/getGenres.view', methods=["GET", "POST"])
def genres():
    res_format = request.values.get('f') or 'xml'
    with g.lib.transaction() as tx:
        mixed_genres = list(tx.query("""
            SELECT genre, COUNT(*) AS n_song, "" AS n_album FROM items GROUP BY genre
            UNION ALL
            SELECT genre, "" AS n_song, COUNT(*) AS n_album FROM albums GROUP BY genre
        """))

    genres = {}
    for genre in mixed_genres:
        key = genre[0]
        if (not key in genres.keys()):
            genres[key] = (genre[1], 0)
        if (genre[2]):
            genres[key] = (genres[key][0], genre[2])

    genres = [(k, v[0], v[1]) for k, v in genres.items()]
    # genres.sort(key=lambda genre: strip_accents(genre[0]).upper())
    genres.sort(key=lambda genre: genre[1])
    genres.reverse()
    genres = filter(lambda genre: genre[0] != u"", genres)

    if (is_json(res_format)):
        def map_genre(genre):
            return {
                "value": genre[0],
                "songCount": genre[1],
                "albumCount": genre[2]
            }

        return jsonpify(request, wrap_res("genres", {
            "genre": list(map(map_genre, genres))
        }))
    else:
        root = get_xml_root()
        genres_xml = ET.SubElement(root, 'genres')

        for genre in genres:
            genre_xml = ET.SubElement(genres_xml, 'genre')
            genre_xml.text = genre[0]
            genre_xml.set("songCount", str(genre[1]))
            genre_xml.set("albumCount", str(genre[2]))

        return Response(xml_to_string(root), mimetype='text/xml')


@app.route('/rest/getSong', methods=["GET", "POST"])
@app.route('/rest/getSong.view', methods=["GET", "POST"])
def song():
    res_format = request.values.get('f') or 'xml'
    id = int(song_subid_to_beetid(request.values.get('id')))
    song = g.lib.get_item(id)

    if (is_json(res_format)):
        return jsonpify(request, wrap_res("song", map_song(song)))
    else:
        root = get_xml_root()
        s = ET.SubElement(root, 'song')
        map_song_xml(s, song)

        return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getSongsByGenre', methods=["GET", "POST"])
@app.route('/rest/getSongsByGenre.view', methods=["GET", "POST"])
def songs_by_genre():
    res_format = request.values.get('f') or 'xml'
    genre = request.values.get('genre')
    count = int(request.values.get('count') or 10)
    offset = int(request.values.get('offset') or 0)

    songs = handleSizeAndOffset(list(g.lib.items('genre:' + genre.replace("'", "\\'"))), count, offset)

    if (is_json(res_format)):
        return jsonpify(request, wrap_res("songsByGenre", {
            "song": list(map(map_song, songs))
        }))
    else:
        root = get_xml_root()
        songs_by_genre = ET.SubElement(root, 'songsByGenre')

        for song in songs:
            s = ET.SubElement(songs_by_genre, 'song')
            map_song_xml(s, song)

        return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getAlbum', methods=["GET", "POST"])
@app.route('/rest/getAlbum.view', methods=["GET", "POST"])
def get_album():
    res_format = request.values.get('f') or 'xml'
    id = int(album_subid_to_beetid(request.values.get('id')))

    album = g.lib.get_album(id)
    songs = sorted(album.items(), key=lambda song: song.track)

    if (is_json(res_format)):
        res = wrap_res("album", {
            **map_album(album),
            **{ "song": list(map(map_song, songs)) }
        })
        return jsonpify(request, res)
    else:
        root = get_xml_root()
        albumXml = ET.SubElement(root, 'album')
        map_album_xml(albumXml, album)

        for song in songs:
            s = ET.SubElement(albumXml, 'song')
            map_song_xml(s, song)

        return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getAlbumList', methods=["GET", "POST"])
@app.route('/rest/getAlbumList.view', methods=["GET", "POST"])
def album_list():
    return get_album_list(1)


@app.route('/rest/getAlbumList2', methods=["GET", "POST"])
@app.route('/rest/getAlbumList2.view', methods=["GET", "POST"])
def album_list_2():
    return get_album_list(2)

def get_album_list(version):
    res_format = request.values.get('f') or 'xml'
    # TODO possibleTypes = ['random', 'frequent', 'recent', 'starred']
    sort_by = request.values.get('type') or 'alphabeticalByName' # TODO
    size = int(request.values.get('size') or 10)
    offset = int(request.values.get('offset') or 0)
    fromYear = int(request.values.get('fromYear') or 0)
    toYear = int(request.values.get('toYear') or 3000)
    genre = request.values.get('genre')

    albums = list(g.lib.albums())

    if sort_by == 'newest':
        albums.sort(key=lambda album: int(dict(album)['added']), reverse=True)
    elif sort_by == 'alphabeticalByName':
        albums.sort(key=lambda album: strip_accents(dict(album)['album']).upper())
    elif sort_by == 'alphabeticalByArtist':
        albums.sort(key=lambda album: strip_accents(dict(album)['albumartist']).upper())
    elif sort_by == 'alphabeticalByArtist':
        albums.sort(key=lambda album: strip_accents(dict(album)['albumartist']).upper())
    elif sort_by == 'byGenre':
        albums = filter(lambda album: dict(album)['genre'].lower() == genre.lower(), albums)
    elif sort_by == 'byYear':
        # TODO use month and day data to sort
        if fromYear <= toYear:
            albums = list(filter(lambda album: dict(album)['year'] >= fromYear and dict(album)['year'] <= toYear, albums))
            albums.sort(key=lambda album: int(dict(album)['year']))
        else:
            albums = list(filter(lambda album: dict(album)['year'] >= toYear and dict(album)['year'] <= fromYear, albums))
            albums.sort(key=lambda album: int(dict(album)['year']), reverse=True)

    albums = handleSizeAndOffset(albums, size, offset)

    if version == 1:
        if (is_json(res_format)):
            return jsonpify(request, wrap_res("albumList", {
                "album": list(map(map_album_list, albums))
            }))
        else:
            root = get_xml_root()
            album_list_xml = ET.SubElement(root, 'albumList')

            for album in albums:
                a = ET.SubElement(album_list_xml, 'album')
                map_album_list_xml(a, album)

            return Response(xml_to_string(root), mimetype='text/xml')

    elif version == 2:
        if (is_json(res_format)):
            return jsonpify(request, wrap_res("albumList2", {
                "album": list(map(map_album, albums))
            }))
        else:
            root = get_xml_root()
            album_list_xml = ET.SubElement(root, 'albumList2')

            for album in albums:
                a = ET.SubElement(album_list_xml, 'album')
                map_album_xml(a, album)

            return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getCoverArt', methods=["GET", "POST"])
@app.route('/rest/getCoverArt.view', methods=["GET", "POST"])
def cover_art_file():
    query_id = int(album_subid_to_beetid(request.values.get('id')) or -1)
    size = request.values.get('size')
    album = g.lib.get_album(query_id)

    # Fallback on item id. Some apps use this
    if not album:
        item = g.lib.get_item(query_id)
        if item is not None and item.album_id is not None:
            album = g.lib.get_album(item.album_id)
        else:
            flask.abort(404)

    if album and album.artpath:
        image_path = album.artpath.decode('utf-8')

        if size is not None and int(size) > 0:
            size = int(size)
            with Image.open(image_path) as image:
                bytes_io = io.BytesIO()
                image = image.resize((size, size))
                image.convert('RGB').save(bytes_io, 'PNG')
                bytes_io.seek(0)
                return flask.send_file(bytes_io, mimetype='image/png')

        return flask.send_file(image_path)
    else:
        return flask.abort(404)

# Artists

@app.route('/rest/getArtists', methods=["GET", "POST"])
@app.route('/rest/getArtists.view', methods=["GET", "POST"])
def all_artists():
    return get_artists("artists")

@app.route('/rest/getIndexes', methods=["GET", "POST"])
@app.route('/rest/getIndexes.view', methods=["GET", "POST"])
def indexes():
    return get_artists("indexes")

def get_artists(version):
    res_format = request.values.get('f') or 'xml'
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

    if (is_json(res_format)):
        indicies = []
        for index, artist_names in indicies_dict.items():
            indicies.append({
                "name": index,
                "artist": list(map(map_artist, artist_names))
            })

        return jsonpify(request, wrap_res(version, {
            "ignoredArticles": "",
            "lastModified": int(time.time() * 1000),
            "index": indicies
        }))
    else:
        root = get_xml_root()
        indexes_xml = ET.SubElement(root, version)
        indexes_xml.set('ignoredArticles', "")

        indicies = []
        for index, artist_names in indicies_dict.items():
            indicies.append({
                "name": index,
                "artist": artist_names
            })

        for index in indicies:
            index_xml = ET.SubElement(indexes_xml, 'index')
            index_xml.set('name', index["name"])

            for a in index["artist"]:
                artist = ET.SubElement(index_xml, 'artist')
                map_artist_xml(artist, a)

        return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getMusicDirectory', methods=["GET", "POST"])
@app.route('/rest/getMusicDirectory.view', methods=["GET", "POST"])
def musicDirectory():
    # Works pretty much like a file system
    # Usually Artist first, than Album, than Songs
    res_format = request.values.get('f') or 'xml'
    id = request.values.get('id')

    if id.startswith(ARTIST_ID_PREFIX):
        artist_id = id
        artist_name = artist_id_to_name(artist_id)
        albums = g.lib.albums(artist_name.replace("'", "\\'"))
        albums = filter(lambda album: album.albumartist == artist_name, albums)

        if (is_json(res_format)):
            return jsonpify(request, wrap_res("directory", {
                "id": artist_id,
                "name": artist_name,
                "child": list(map(map_album, albums))
            }))
        else:
            root = get_xml_root()
            artist_xml = ET.SubElement(root, 'directory')
            artist_xml.set("id", artist_id)
            artist_xml.set("name", artist_name)

            for album in albums:
                a = ET.SubElement(artist_xml, 'child')
                map_album_xml(a, album)

            return Response(xml_to_string(root), mimetype='text/xml')
    elif id.startswith(ALBUM_ID_PREFIX):
        # Album
        id = int(album_subid_to_beetid(id))
        album = g.lib.get_album(id)
        songs = sorted(album.items(), key=lambda song: song.track)

        if (is_json(res_format)):
            res = wrap_res("directory", {
                **map_album(album),
                **{ "child": list(map(map_song, songs)) }
            })
            return jsonpify(request, res)
        else:
            root = get_xml_root()
            albumXml = ET.SubElement(root, 'directory')
            map_album_xml(albumXml, album)

            for song in songs:
                s = ET.SubElement(albumXml, 'child')
                map_song_xml(s, song)

            return Response(xml_to_string(root), mimetype='text/xml')
    elif id.startswith(SONG_ID_PREFIX):
        # Song
        id = int(song_subid_to_beetid(id))
        song = g.lib.get_item(id)

        if (is_json(res_format)):
            return jsonpify(request, wrap_res("directory", map_song(song)))
        else:
            root = get_xml_root()
            s = ET.SubElement(root, 'directory')
            map_song_xml(s, song)

            return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getArtist', methods=["GET", "POST"])
@app.route('/rest/getArtist.view', methods=["GET", "POST"])
def artist():
    res_format = request.values.get('f') or 'xml'
    artist_id = request.values.get('id')
    artist_name = artist_id_to_name(artist_id)
    albums = g.lib.albums(artist_name.replace("'", "\\'"))
    albums = filter(lambda album: album.albumartist == artist_name, albums)

    if (is_json(res_format)):
        return jsonpify(request, wrap_res("artist", {
            "id": artist_id,
            "artist_name": artist_name,
            "album": list(map(map_album, albums))
        }))
    else:
        root = get_xml_root()
        artist_xml = ET.SubElement(root, 'artist')
        artist_xml.set("id", artist_id)
        artist_xml.set("artist_name", artist_name)

        for album in albums:
            a = ET.SubElement(artist_xml, 'album')
            map_album_xml(a, album)

        return Response(xml_to_string(root), mimetype='text/xml')

@app.route('/rest/getArtistInfo2', methods=["GET", "POST"])
@app.route('/rest/getArtistInfo2.view', methods=["GET", "POST"])
def artistInfo2():
    res_format = request.values.get('f') or 'xml'
    artist_name = artist_id_to_name(request.values.get('id'))

    if (is_json(res_format)):
        return jsonpify(request, wrap_res("artistInfo2", {
            "biography": f"wow. much artist. very {artist_name}",
            "musicBrainzId": "",
            "lastFmUrl": "",
            "smallImageUrl": "",
            "mediumImageUrl": "",
            "largeImageUrl": ""
        }))
    else:
        root = get_xml_root()
        artist_xml = ET.SubElement(root, 'artistInfo2')

        biography = ET.SubElement(artist_xml, "biography")
        biography.text = f"wow. much artist very {artist_name}."
        musicBrainzId = ET.SubElement(artist_xml, "musicBrainzId")
        musicBrainzId.text = ""
        lastFmUrl = ET.SubElement(artist_xml, "lastFmUrl")
        lastFmUrl.text = ""
        smallImageUrl = ET.SubElement(artist_xml, "smallImageUrl")
        smallImageUrl.text = ""
        mediumImageUrl = ET.SubElement(artist_xml, "mediumImageUrl")
        mediumImageUrl.text = ""
        largeImageUrl = ET.SubElement(artist_xml, "largeImageUrl")
        largeImageUrl.text = ""

        return Response(xml_to_string(root), mimetype='text/xml')

# Users.

@app.route('/rest/getUser', methods=["GET", "POST"])
@app.route('/rest/getUser.view', methods=["GET", "POST"])
def user():
    res_format = request.values.get('f') or 'xml'
    if (is_json(res_format)):
        return jsonpify(request, wrap_res("user", {
            "username" : "admin",
            "email" : "foo@example.com",
            "scrobblingEnabled" : True,
            "adminRole" : True,
            "settingsRole" : True,
            "downloadRole" : True,
            "uploadRole" : True,
            "playlistRole" : True,
            "coverArtRole" : True,
            "commentRole" : True,
            "podcastRole" : True,
            "streamRole" : True,
            "jukeboxRole" : True,
            "shareRole" : True,
            "videoConversionRole" : True,
            "avatarLastChanged" : "1970-01-01T00:00:00.000Z",
            "folder" : [ 0 ]
        }))
    else:
        root = get_xml_root()
        u = ET.SubElement(root, 'user')
        u.set("username", "admin")
        u.set("email", "foo@example.com")
        u.set("scrobblingEnabled", "true")
        u.set("adminRole", "true")
        u.set("settingsRole", "true")
        u.set("downloadRole", "true")
        u.set("uploadRole", "true")
        u.set("playlistRole", "true")
        u.set("coverArtRole", "true")
        u.set("commentRole", "true")
        u.set("podcastRole", "true")
        u.set("streamRole", "true")
        u.set("jukeboxRole", "true")
        u.set("shareRole", "true")
        u.set("videoConversionRole", "true")
        u.set("avatarLastChanged", "1970-01-01T00:00:00.000Z")
        f = ET.SubElement(u, 'folder')
        f.text = "0"

        return Response(xml_to_string(root), mimetype='text/xml')

# UI.

@app.route('/')
def home():
    return "Beets-SubSonic-API running"


# Plugin hook.

class SubSonicPlugin(BeetsPlugin):
    def __init__(self):
        super(SubSonicPlugin, self).__init__()
        self.config.add({
            'host': u'127.0.0.1',
            'port': 8080,
            'cors': '*',
            'cors_supports_credentials': True,
            'reverse_proxy': False,
            'include_paths': False,
        })

    def commands(self):
        cmd = ui.Subcommand('subsonic', help=u'expose a SubSonic API')
        cmd.parser.add_option(u'-d', u'--debug', action='store_true',
                              default=False, help=u'debug mode')

        def func(lib, opts, args):
            args = ui.decargs(args)
            if args:
                self.config['host'] = args.pop(0)
            if args:
                self.config['port'] = int(args.pop(0))

            app.config['lib'] = lib
            # Normalizes json output
            app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

            app.config['INCLUDE_PATHS'] = self.config['include_paths']

            # Enable CORS if required.
            if self.config['cors']:
                self._log.info(u'Enabling CORS with origin: {0}',
                               self.config['cors'])
                app.config['CORS_ALLOW_HEADERS'] = "Content-Type"
                app.config['CORS_RESOURCES'] = {
                    r"/*": {"origins": self.config['cors'].get(str)}
                }
                CORS(
                    app,
                    supports_credentials=self.config[
                        'cors_supports_credentials'
                    ].get(bool)
                )

            # Allow serving behind a reverse proxy
            if self.config['reverse_proxy']:
                app.wsgi_app = ReverseProxied(app.wsgi_app)

            # Start the web application.
            app.run(host=self.config['host'].as_str(),
                    port=self.config['port'].get(int),
                    debug=opts.debug, threaded=True)
        cmd.func = func
        return [cmd]


class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    From: http://flask.pocoo.org/snippets/35/

    :param app: the WSGI application
    '''
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)
