from beetsplug.beetstream import ALBUM_ID_PREFIX, ARTIST_ID_PREFIX, SONG_ID_PREFIX
import unicodedata
from datetime import datetime
import flask
import json
import base64
import mimetypes
import enum
import xml.etree.cElementTree as ET
from math import ceil

class SubsonicErrorCode(enum.IntEnum):
    GENERIC_ERROR = 0    # A generic error
    MISSING_PARAM = 10   # Required parameter is missing.
    CLIENT_TOO_OLD = 20  # Incompatible Subsonic REST protocol version. Client must upgrade.
    SERVER_TOO_OLD = 30  # Incompatible Subsonic REST protocol version. Server must upgrade.
    INVALID_AUTH = 40    # Wrong username or password.
    UNAUTHORIZED = 50    # User is not authorized for the given operation.
    NOT_FOUND = 70       # The requested data was not found.

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def timestamp_to_iso(timestamp):
    return datetime.fromtimestamp(int(timestamp)).isoformat()

class Attr:
    __xml_type__ = 'Attr'
    def __init__(self, s):
        self.s = s

    def __str__(self):
        return self.s

    def __repr__(self):
        return self.s

class Elem:
    __xml_type__ = 'Elem'
    def __init__(self, s):
        self.s = s

    def __str__(self):
        return self.s

    def __repr__(self):
        return self.s

class ElemText:
    def __init__(self, s):
        self.s = s

    def __str__(self):
        return self.s

    def __repr__(self):
        return self.s

def response_to_json(d):
    ret = {}
    for k, v in d.items():
        if type(v) is dict:
            ret[str(k)] = response_to_json(d[k])
        else:
            ret[str(k)] = v
    return ret

def response_to_xml(d, parent=None):
    def stringify(v):
        if type(v) is bool:
            return "true" if v else "false"
        return str(v)

    assert(len(d.keys()) == 1)
    name = list(d.keys())[0]

    element = ET.Element(name) if parent is None else ET.SubElement(parent, name)
    for k, v in d[name].items():
        if isinstance(k, Attr):
            k = k.s
            element.set(k, stringify(v))
        elif isinstance(k, ElemText):
            element.text = v
        elif isinstance(k, Elem):
            k = k.s
            if type(v) is dict:
                response_to_xml({k: v}, parent=element)
            else:
                sub = ET.SubElement(element, k)
                sub.text = stringify(v)
        else:
            if type(v) is list:
                for val in v:
                    if type(val) is dict:
                        response_to_xml({k: val}, parent=element)
                    else:
                        sub = ET.SubElement(element, k)
                        sub.text = stringify(val)
            elif type(v) is dict:
                response_to_xml({k: v}, parent=element)
            else:
                element.set(k, stringify(v))

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
        xml = ET.tostring(response_to_xml(response), encoding='unicode')
        return flask.Response(xml, mimetype='text/xml')
    else:
        response = response_to_json(response)
        if fmt == "jsonp":
            callback = request.values.get("callback")
            return f"{callback}({json.dumps(response)});"
        else:
            return flask.jsonify(response)

def subsonic_response_error(request, code, message=""):
    d = {
        "error": {
            "code": code,
            "message": message,
        }
    }

    return subsonic_response(request, d, ok=False)

def map_album(album):
    return {
        "id": album_beetid_to_subid(str(album.id)),
        "name": album.album,
        "title": album.album,
        "album": album.album,
        "artist": album.albumartist,
        "artistId": artist_name_to_id(album.albumartist),
        "parent": artist_name_to_id(album.albumartist),
        "isDir": True,
        "coverArt": album_beetid_to_subid(str(album.id)) or "",
        "songCount": 1, # TODO
        "duration": 1, # TODO
        "playCount": 1, # TODO
        "created": timestamp_to_iso(album.added),
        "year": album.year,
        "genre": album.genre,
        "starred": "1970-01-01T00:00:00.000Z", # TODO
        "averageRating": 0 # TODO
    }

def map_song(item):
    path = item.path.decode('utf-8')
    return {
        "id": song_beetid_to_subid(str(item.id)),
        "parent": album_beetid_to_subid(str(item.album_id)),
        "isDir": False,
        "title": item.title,
        "name": item.title,
        "album": item.album,
        "artist": item.albumartist,
        "track": item.track,
        "year": item.year,
        "genre": item.genre,
        "coverArt": album_beetid_to_subid(str(item.album_id)) or "",
        "size": item.filesize,
        "contentType": mimetypes.guess_type(path)[0],
        "suffix": item.format.lower(),
        "duration": ceil(item.length),
        "bitRate": ceil(item.bitrate/1000),
        "path": path,
        "playCount": 1, #TODO
        "created": timestamp_to_iso(item.added),
        # "starred": "2019-10-23T04:41:17.107Z",
        "albumId": album_beetid_to_subid(str(item.album_id)),
        "artistId": artist_name_to_id(item.albumartist),
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
