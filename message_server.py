import json
import logging
import os
from urllib import parse
from http.server import HTTPServer, BaseHTTPRequestHandler


def make_server_handler(movement_callback=None, stat_callback=None):
    class ServerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = parse.urlparse(self.path)
            params = parse.parse_qs(self.path[2:])
            if parsed.path == "/":
                if 'move' in params and movement_callback is not None:
                    move_params = params['move'][0].replace(" ", "")
                    movement_callback(move_params)
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(
                        f"Spot is now going to {move_params}".encode('utf-8'))
                elif 'stat' in params and stat_callback is not None:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    with open(os.path.join('assets', "statpage.htm"), 'rb') as rf:
                        self.wfile.write(rf.read())
                else:
                    self.send_response(400)
            elif parsed.path == "/battery" or parsed.path == "/viewcount" or parsed.path == "/lastcommand":
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(stat_callback(parsed.path[1:])).encode('utf-8'))
            else:
                logging.info(parsed.path)
                self.send_response(400)

        def log_message(self, formats, *args) -> None:
            pass

    return ServerHandler


class Server:
    def __init__(self, movement_callback=None, stat_callback=None):
        logging.info(f"Creating message server")
        self._movement_callback = movement_callback
        self._stat_callback = stat_callback

    def start(self, port=80):
        logging.info(f'Starting server on port {port}')
        server_address = ('', port)
        httpd = HTTPServer(
            server_address,
            make_server_handler(
                movement_callback=self._movement_callback,
                stat_callback=self._stat_callback
            )
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        httpd.server_close()
