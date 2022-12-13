from beetsplug.beetstream import ALBUM_ID_PREFIX, ARTIST_ID_PREFIX, SONG_ID_PREFIX
import unicodedata
from datetime import datetime
import flask
import json
import base64
import mimetypes
import os
import xml.etree.cElementTree as ET
from math import ceil
from xml.dom import minidom

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def timestamp_to_iso(timestamp):
    return datetime.fromtimestamp(int(timestamp)).isoformat()

def response_to_xml(d, parent=None):
    assert(len(d.keys()) == 1)
    name = list(d.keys())[0]

    element = ET.Element(name) if parent is None else ET.SubElement(parent, name)
    for k, v in d[name].items():
        if type(v) is list:
            for val in v:
                if type(val) is dict:
                    response_to_xml({k: val}, parent=element)
                else:
                    sub = ET.SubElement(element, k)
                    sub.text = str(val)
        elif type(v) is dict:
            response_to_xml({k: v}, parent=element)
        else:
            element.set(k, str(v))

    return element

def subsonic_response(request, d, ok=True):
    fmt = request.values.get('f') or 'xml'

    response = {
        "subsonic-response": {
            "status": "ok" if ok else "failed",
            "version": "1.16.1",
            **d,
        }
    }

    if fmt == "xml":
        response["subsonic-response"]["xmlns"] = "http://subsonic.org/restapi"
        xml = response_to_xml(response)
        return flask.Response(xml_to_string(xml), mimetype='text/xml')
    else:
        return jsonpify(request, response)

def subsonic_response_error(request, code, message=""):
    d = {
        "error": {
            "code": code,
            "message": message,
        }
    }

    return subsonic_response(request, d, ok=False)

def jsonpify(request, data):
    if request.values.get("f") == "jsonp":
        callback = request.values.get("callback")
        return f"{callback}({json.dumps(data)});"
    else:
        return flask.jsonify(data)

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

def map_song(song):
    song = dict(song)
    path = song["path"].decode('utf-8')
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
        "size": os.path.getsize(path),
        "contentType": mimetypes.guess_type(path)[0],
        "suffix": song["format"].lower(),
        "duration": ceil(song["length"]),
        "bitRate": ceil(song["bitrate"]/1000),
        "path": path,
        "playCount": 1, #TODO
        "created": timestamp_to_iso(song["added"]),
        # "starred": "2019-10-23T04:41:17.107Z",
        "albumId": album_beetid_to_subid(str(song["album_id"])),
        "artistId": artist_name_to_id(song["albumartist"]),
        "type": "music"
    }

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
