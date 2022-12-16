from beetsplug.beetstream import app
from beetsplug.beetstream.utils import *
from hashlib import md5
import flask
from flask import request

password_cache = {}

def get_password(user):
    if user in password_cache:
        return password_cache[user]

    users = app.config['config']['users']
    if user not in users:
        return None
    user_conf = users[user]

    if 'password' in user_conf:
        password = user_conf['password']
    elif 'passwordFile' in users[user]:
        with open(user_conf['passwordFile'], 'r') as f:
            password = f.read()

    password_cache[user] = password
    return password

def authorized(password, salt, token):
    concat = (str(password) + salt).encode('utf-8')
    return md5(concat).hexdigest() == token

@app.before_request
def handle_auth():
    # Allow all users through by default.
    if 'users' not in app.config['config']:
        return

    user = request.values.get('u')
    salt = request.values.get('s')
    token = request.values.get('t')

    if user is None or salt is None or token is None:
        return subsonic_response_error(request, SubsonicErrorCode.MISSING_PARAM,
                                       "missing required parameter for auth")
    password = get_password(user)
    if password is None:
        return subsonic_response_error(request, SubsonicErrorCode.INVALID_AUTH,
                                       "unknown username")

    if not authorized(password, salt, token):
        return subsonic_response_error(request, SubsonicErrorCode.INVALID_AUTH,
                                       "incorrect password")
