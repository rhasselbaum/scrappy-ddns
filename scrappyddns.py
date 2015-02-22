import logging.handlers
import os
from flask import Flask, abort, request
import time
import re
import sys
import urllib.parse
import json
import traceback
import tempfile
import http.client
import ssl

# Create app. Look for config file in module dir or dir in environment variable.
app = Flask(__name__)


class ScrappyException(Exception):
    """Represents a service failure."""
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


def update_ip(ip_filename, client_name, client_ip):
    """Save the IP address in the given file and send a notification."""
    # Do the push first so if there is any error, we'll try again next time.
    push_notify(client_name, client_ip)
    # Update the IP file atomically, since others could be accessing it.
    with tempfile.NamedTemporaryFile('w', dir=os.path.dirname(ip_filename), delete=False) as tmp_file:
        tmp_file.write(client_ip)
        tmp_filename = tmp_file.name
    os.rename(tmp_filename, ip_filename)


def create_secure_conn():
    """Create and return HTTPSConnection to the push service."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    context.verify_mode = ssl.CERT_REQUIRED
    ca_file = os.path.join(os.path.dirname(__file__), 'pushover-ca.pem')
    context.load_verify_locations(ca_file)
    return http.client.HTTPSConnection('api.pushover.net', 443, context=context)


def push_notify(client_name, client_ip):
    """Make the push notification request.

    Raises exception if push fails."""
    # Make sure we have the required keys.
    user_key = app.config.get('PUSHOVER_USER_KEY')
    if not user_key:
        raise ScrappyException('No Pushover user key given. Set PUSHOVER_USER_KEY in the config file.')
    app_key = app.config.get('PUSHOVER_APP_KEY')
    if not app_key:
        raise ScrappyException('No Pushover application key given. Set PUSHOVER_APP_KEY in the config file.')

    # Assemble the request data
    notification = '{0} is at {1}'.format(client_name, client_ip)
    post_attribs = dict(token=app_key,
                        user=user_key,
                        priority=app.config.get('PUSHOVER_MSG_PRIORITY', 0),
                        title='IP address update',
                        message=notification)
    post_data = urllib.parse.urlencode(post_attribs).encode('utf-8')
    headers = {'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'}

    # Make the request.
    conn = None
    try:
        conn = create_secure_conn()
        # Make the request, get the response.
        conn.request('POST', '/1/messages.json', body=post_data, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read().decode('utf-8')
        app.logger.debug('Web service response: %s', resp_body)
        if resp.status == http.client.OK or resp.status in range(400, 500):
            # Expecting a JSON body with a 'status' element.
            resp_dict = json.loads(resp_body)
            if resp.status == http.client.OK and resp_dict.get('status') == 1:
                # We're good!
                app.logger.info('Push succeeded: %s', notification)
            else:
                # Something went wrong. Look for an 'errors' array with details.
                resp_errors = resp_dict.get('errors')
                raise ScrappyException('Push failed with error {0}: {1}'
                                       .format(resp.status, resp_errors if resp_errors else resp_dict))
        else:
            # Server-side error 500, most likely.
            raise ScrappyException('Push failed with HTTP status: {0}'.format(resp.status))
    except ScrappyException:
        raise
    except:
        # A general connectivity failure or unexpected response format.
        raise ScrappyException('Push failed with: {0}'.format(sys.exc_info()[1]))
    finally:
        if conn:
            conn.close()


def load_tokens(token_list_filename):
    """Load token list from the file.

    Args:
        token_list_filename- Path to the token list file.

    Returns a dict of tokens to friendly names. Raises exception if the file is not found or there are no tokens."""
    token_names = None
    if os.path.isfile(token_list_filename):
        with open(token_list_filename) as token_file:
            # Convert lines of the form "<token>:<name>" from the file into an equivalent dict. Ignore comments.
            token_lines = [line.strip() for line in token_file.readlines() if re.match(r'[^#].*:.*', line)]
            token_names = {elem[0]: elem[1] for elem in [line.split(':') for line in token_lines]}
    if not token_names:
        raise ScrappyException('Token list file [{0}] is missing or contains no tokens.'.format(token_list_filename))
    return token_names


@app.route("/<token>")
def hello(token):
    """Check to see if token matches a known one and if client IP has changed, push a notification."""
    try:
        token_list_filename = app.config.get('TOKEN_LIST_FILE', 'token.list')
        token_names = load_tokens(token_list_filename)
        if token in token_names:
            # The URL contains a recognized token. IP address comes from a parameter (if given) or the source IP.
            client_name = token_names[token]
            client_ip = request.args.get('ip_address', request.remote_addr)
            app.logger.debug('Received ping from [%s] @ %s.', client_name, client_ip)
            # Old IP address, if known, is contained in a "<token>.ip" file in the cache directory.
            cache_dir = app.config.get('IP_ADDRESS_CACHE', '.')
            ip_filename = os.path.join(cache_dir, token + '.ip')
            if os.path.isfile(ip_filename):
                # We've seen this token before. But we won't take action if the IP file was modified less than
                # 10 seconds ago to avoid a flood.
                cutoff = time.time() - 10
                if os.stat(ip_filename).st_mtime < cutoff:
                    # IP file has not been modified too recently.
                    with open(ip_filename) as ip_file:
                        old_ip = ip_file.read()
                    if old_ip != client_ip:
                        # Alert! IP address has changed!
                        update_ip(ip_filename, client_name, client_ip)
                    else:
                        # IP address is the same.
                        app.logger.debug('IP of [%s] has not changed from %s. Ignored ping.',
                                         client_name, client_ip)
                else:
                    # Too many pings! We're getting flooded!
                    app.logger.debug('Ignored extra ping from [%s] @ %s. Too many in a short period.',
                                     client_name, client_ip)
            else:
                # Haven't seen this token before. Alert!
                update_ip(ip_filename, client_name, client_ip)
            return 'OK'
        else:
            # The URL has no recognized token. Go away!
            abort(404)
    except Exception as e:
        app.logger.error(e)
        if app.debug:
            traceback.print_exc()
        abort(500)


def init_logging():
    """Initialize logging to the specified file or stdout if none was given in the config."""
    log_file = app.config.get('LOG_FILE')
    if log_file:
        log_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=5)
    else:
        log_handler = logging.StreamHandler(sys.stdout)
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    log_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    app.logger.setLevel(log_level)
    app.logger.addHandler(log_handler)


# Initialize the Flask app instance.
app.config.from_pyfile('scrappyddns.conf', silent=True)
app.config.from_envvar('SCRAPPYDDNS_CONF', silent=True)
init_logging()

# Start embedded server if run as a script.
if __name__ == "__main__":
    # And GO!
    host = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    app.run(host=host, port=port)
