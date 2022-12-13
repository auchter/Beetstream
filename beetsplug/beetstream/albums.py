from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
import flask
from flask import g, request
from PIL import Image
import io
from random import shuffle
from beets.dbcore.query import (
    AndQuery,
    MatchQuery,
)


@app.route('/rest/getAlbum', methods=["GET", "POST"])
@app.route('/rest/getAlbum.view', methods=["GET", "POST"])
def get_album():
    id = int(album_subid_to_beetid(request.values.get('id')))

    album = g.lib.get_album(id)
    songs = sorted(album.items(), key=lambda song: song.track)

    return subsonic_response(request, {
        'album': {
            **map_album(album),
            "song": list(map(map_song, songs)),
        }
    })

@app.route('/rest/getAlbumList', methods=["GET", "POST"])
@app.route('/rest/getAlbumList.view', methods=["GET", "POST"])
def album_list():
    return get_album_list(1)


@app.route('/rest/getAlbumList2', methods=["GET", "POST"])
@app.route('/rest/getAlbumList2.view', methods=["GET", "POST"])
def album_list_2():
    return get_album_list(2)

def get_album_list(version):
    # TODO type == 'starred' and type == 'frequent'
    sort_by = request.values.get('type') or 'alphabeticalByName'
    size = int(request.values.get('size') or 10)
    offset = int(request.values.get('offset') or 0)
    fromYear = int(request.values.get('fromYear') or 0)
    toYear = int(request.values.get('toYear') or 3000)
    genre = request.values.get('genre')

    albums = list(g.lib.albums())

    if sort_by == 'newest':
        albums.sort(key=lambda album: int(album.added), reverse=True)
    elif sort_by == 'alphabeticalByName':
        albums.sort(key=lambda album: strip_accents(album.album).upper())
    elif sort_by == 'alphabeticalByArtist':
        albums.sort(key=lambda album: strip_accents(album.albumartist).upper())
    elif sort_by == 'alphabeticalByArtist':
        albums.sort(key=lambda album: strip_accents(album.albumartist).upper())
    elif sort_by == 'recent':
        albums.sort(key=lambda album: album.year, reverse=True)
    elif sort_by == 'byGenre':
        albums = list(filter(lambda album: album.genre.lower() == genre.lower(), albums))
    elif sort_by == 'byYear':
        # TODO use month and day data to sort
        if fromYear <= toYear:
            albums = list(filter(lambda album: album.year >= fromYear and album.year <= toYear, albums))
            albums.sort(key=lambda album: int(album.year))
        else:
            albums = list(filter(lambda album: album.year >= toYear and album.year <= fromYear, albums))
            albums.sort(key=lambda album: int(album.year), reverse=True)
    elif sort_by == 'random':
        shuffle(albums)

    albums = handleSizeAndOffset(albums, size, offset)

    if version == 1:
        def map_album(album):
            return {
                'id': album_beetid_to_subid(album.id),
                'parent': artist_name_to_id(album.albumartist),
                'isDir': True,
                'title': album.album,
                'album': album.album,
                'artist': album.albumartist,
                'year': album.year,
                'coverArt': album_beetid_to_subid(album.id),
                'created': timestamp_to_iso(album.added),
                'playCount': 0,
                # starred
                # userRating
                # averageRating
            }

        return subsonic_response(request, {
            "albumList": {
                "album": list(map(map_album, albums)),
            }
        })
    elif version == 2:
        def map_album(album):
            query = AndQuery([
                MatchQuery("album", album['album']),
                MatchQuery("albumartist", album['albumartist']),
            ])
            items = g.lib.items(query=query)
            return {
                'id': album_beetid_to_subid(album.id),
                'name': album.album,
                'artist': album.albumartist,
                'artistId': artist_name_to_id(album.albumartist),
                'coverArt': album_beetid_to_subid(album.id),
                'songCount': len(items),
                'duration': int(sum([item['length'] for item in items])),
                'created': timestamp_to_iso(album.added),
                'year': album.year,
                'genre': album.genre,
            }
        return subsonic_response(request, {
            "albumList2": {
                "album": list(map(map_album, albums))
            }
        })

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

@app.route('/rest/getGenres', methods=["GET", "POST"])
@app.route('/rest/getGenres.view', methods=["GET", "POST"])
def genres():
    with g.lib.transaction() as tx:
        def get_genres(table):
            return {k: v for k, v in tx.query(f"SELECT genre, COUNT(*) FROM {table} GROUP BY genre") if k != ''}
        item_genres = get_genres("items")
        album_genres = get_genres("albums")

    def mk_genre(genre):
        return {
            ElemText("value"): genre,
            "songCount": item_genres.get(genre, 0),
            "albumCount": album_genres.get(genre, 0)
        }

    all_genres = set(item_genres.keys()) | set(album_genres.keys())
    genres = [mk_genre(genre) for genre in all_genres]
    genres.sort(key=lambda genre: genre['albumCount'])
    genres.reverse()

    return subsonic_response(request, {
        "genres": {
            "genre": genres,
        }
    })

@app.route('/rest/getMusicDirectory', methods=["GET", "POST"])
@app.route('/rest/getMusicDirectory.view', methods=["GET", "POST"])
def musicDirectory():
    # Works pretty much like a file system
    # Usually Artist first, than Album, than Songs
    id = request.values.get('id')

    if id.startswith(ARTIST_ID_PREFIX):
        artist_id = id
        artist_name = artist_id_to_name(artist_id)
        albums = g.lib.albums(artist_name.replace("'", "\\'"))
        albums = filter(lambda album: album.albumartist == artist_name, albums)

        return subsonic_response(request, {
            "directory": {
                "id": artist_id,
                "name": artist_name,
                "child": list(map(map_album, albums))
            }
        })
    elif id.startswith(ALBUM_ID_PREFIX):
        # Album
        id = int(album_subid_to_beetid(id))
        album = g.lib.get_album(id)
        songs = sorted(album.items(), key=lambda song: song.track)

        return subsonic_response(request, {
            "directory": {
                **map_album(album),
                "child": list(map(map_song, songs))
            }
        })
    elif id.startswith(SONG_ID_PREFIX):
        # Song
        id = int(song_subid_to_beetid(id))
        song = g.lib.get_item(id)

        return subsonic_response(request, {
            "directory": map_song(song)
        })
