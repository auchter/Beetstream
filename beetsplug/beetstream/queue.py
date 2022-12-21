from beetsplug.beetstream.utils import *
from beetsplug.beetstream import app
from flask import g, request
import datetime


play_queue = {}

@app.route('/rest/savePlayQueue', methods=["GET", "POST"])
@app.route('/rest/savePlayQueue.view', methods=["GET", "POST"])
def savePlayQueue():
    user = request.values.get('u')
    ids = request.values.getlist('id')
    current = request.values.get('current')
    position = request.values.get('position')
    client = request.values.get('c') or 'unknown'

    play_queue[user] = {
        'ids': ids,
        'current': current,
        'position': position,
        'changed': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'changedBy': client,
    }

    return subsonic_response(request, {})

@app.route('/rest/getPlayQueue', methods=["GET", "POST"])
@app.route('/rest/getPlayQueue.view', methods=["GET", "POST"])
def getPlayQueue():
    user = request.values.get('u')

    if user not in play_queue:
        return subsonic_response(request, {})

    q = play_queue[user]

    def mk_entry(subid):
        beetid = int(song_subid_to_beetid(subid))
        song = g.lib.get_item(beetid)

        return map_song(song)

    return subsonic_response(request, {
        'playQueue': {
            Attr('current'): q['current'],
            Attr('position'): q['position'],
            Attr('username'): user,
            Attr('changed'): q['changed'],
            Attr('changedBy'): q['changedBy'],
            "entry": list(map(mk_entry, q['ids'])),
        }
    })
