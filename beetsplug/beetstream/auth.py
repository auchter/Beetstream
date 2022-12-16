from beetsplug.beetstream import app
from beetsplug.beetstream.utils import *
from hashlib import md5
import flask
import binascii
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

def authorized(password, salt, token, supplied_pw):
    if salt is not None and token is not None:
        concat = (str(password) + salt).encode('utf-8')
        return md5(concat).hexdigest() == token
    elif supplied_pw is not None:
        if supplied_pw.startswith('enc:'):
            supplied_pw = binascii.unhexlify(supplied_pw[4:].encode('utf-8'))
        return supplied_pw == str(password)
    return False

@app.before_request
def handle_auth():
    # Allow all users through by default.
    if 'users' not in app.config['config']:
        return

    user = request.values.get('u')
    salt = request.values.get('s')
    token = request.values.get('t')
    pw = request.values.get('p')

    if user is None and ((salt is None or token is None) or (pw is None)):
        return subsonic_response_error(request, SubsonicErrorCode.MISSING_PARAM,
                                       "missing required parameter for auth")
    password = get_password(user)
    if password is None:
        return subsonic_response_error(request, SubsonicErrorCode.INVALID_AUTH,
                                       "unknown username")

    if not authorized(password, salt, token, pw):
        return subsonic_response_error(request, SubsonicErrorCode.INVALID_AUTH,
                                       "incorrect password")
