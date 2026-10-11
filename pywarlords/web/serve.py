"""Serve the browser version locally.

	python3 web/serve.py [PORT] [--data GAME_DIR] [--upload]

then open http://127.0.0.1:PORT/ (default port 8001).

Like `python3 -m warlords`, the server looks for the original game files (--data, $WARLORDS_DATA,
the current folder, ../warlords, the GOG installation on macOS). When it finds them, the page loads
them straight from this server, so nothing has to be chosen in the browser, and saved games are
written back into that folder (as WAR1.SAV ... WAR8.SAV, shared with the desktop version and with DOS
Warlords). --upload ignores local files: the page then asks for them, as it does on a public web site.

The game files are offered only under /local-game/ and the server listens on 127.0.0.1 only.

Use the address 127.0.0.1, not "localhost": on a page whose host name is localhost the pygbag runtime
switches to its developer mode and loads pygame from pygbag's own test server at
http://localhost:8000/archives/repo/ (whatever the page's port), which does not exist here. Requests
for /archives/ that reach this server anyway are redirected to the pygbag CDN. On a real web site
(GitHub Pages) none of this matters.
"""
import argparse
import http.server
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEBROOT = os.path.join(ROOT, 'build', 'web')
CDN = 'https://pygame-web.github.io'
GAME_EXT = ('.exe', '.map', '.pck', '.sjh', '.rjk', '.sav')
SAVE_NAME = re.compile(r'^war[1-8]\.sav$', re.I)
MAX_SAVE = 1 << 20

sys.path.insert(0, ROOT)


def collect_game_files(folder):
	"""{key: path} for the game files of a folder, keys as the page uses them ('WARLORDS.EXE',
	'PICTS/ARMIES.PCK'); names keep their case."""
	files = {}
	for name in sorted(os.listdir(folder)):
		p = os.path.join(folder, name)
		if os.path.isfile(p) and name.lower().endswith(GAME_EXT):
			files[name] = p
		elif os.path.isdir(p) and name.upper() == 'PICTS':
			for n in sorted(os.listdir(p)):
				if n.lower().endswith('.pck') and os.path.isfile(os.path.join(p, n)):
					files['PICTS/' + n] = os.path.join(p, n)
	return files


class Handler(http.server.SimpleHTTPRequestHandler):

	game_dir = None
	game_files = {}

	def __init__(self, *a, **k):
		super().__init__(*a, directory=WEBROOT, **k)

	def end_headers(self):
		self.send_header('Cache-Control', 'no-cache')
		super().end_headers()

	def _send(self, code, body=b'', ctype='application/octet-stream'):
		self.send_response(code)
		self.send_header('Content-Type', ctype)
		self.send_header('Content-Length', str(len(body)))
		self.end_headers()
		if self.command != 'HEAD':
			self.wfile.write(body)

	def _route(self):
		path = self.path.split('?', 1)[0]
		if path.startswith('/archives/'):
			self.send_response(302)
			self.send_header('Location', CDN + self.path)
			self.end_headers()
			return True
		if path.startswith('/local-game/'):
			key = path[len('/local-game/'):]
			if self.game_dir is None:
				self._send(404, b'no local game folder')
			elif key == 'index.json':
				# rescan: saved games may have been added since the start
				Handler.game_files = collect_game_files(self.game_dir)
				body = json.dumps({'files': sorted(self.game_files)}).encode()
				self._send(200, body, 'application/json')
			elif key in self.game_files:
				with open(self.game_files[key], 'rb') as f:
					self._send(200, f.read())
			else:
				self._send(404, b'not found')
			return True
		return False

	def do_GET(self):
		if not self._route():
			super().do_GET()

	def do_HEAD(self):
		if not self._route():
			super().do_HEAD()

	def do_PUT(self):
		"""Saved games written by the page go back into the game folder."""
		path = self.path.split('?', 1)[0]
		name = path[len('/local-game/'):] if path.startswith('/local-game/') else ''
		n = int(self.headers.get('Content-Length') or 0)
		if self.game_dir is None or not SAVE_NAME.match(name) or not 0 < n <= MAX_SAVE:
			self._send(403, b'only WAR1.SAV ... WAR8.SAV can be written')
			return
		data = self.rfile.read(n)
		existing = [e for e in os.listdir(self.game_dir) if e.lower() == name.lower()]
		target = os.path.join(self.game_dir, existing[0] if existing else name.upper())
		with open(target, 'wb') as f:
			f.write(data)
		print("saved", target)
		self._send(200, b'ok')


Handler.extensions_map['.apk'] = 'application/octet-stream'
Handler.extensions_map['.wasm'] = 'application/wasm'


def main(argv=None):
	ap = argparse.ArgumentParser(description="Serve build/web on localhost.")
	ap.add_argument('port', nargs='?', type=int, default=8001)
	ap.add_argument('--data', '-d', help="folder with the original game files")
	ap.add_argument('--upload', action='store_true', help="do not offer local game files; the page asks for them")
	args = ap.parse_args(argv)
	if not os.path.exists(os.path.join(WEBROOT, 'index.html')):
		sys.exit("build/web/index.html not found: run web/build.py first")
	if not args.upload:
		from warlords.__main__ import find_game_dir, game_dir_candidates
		if args.data:
			Handler.game_dir = find_game_dir([args.data])
			if Handler.game_dir is None:
				sys.exit("No Warlords game files (WARLORDS.EXE, PICTS/) in %s" % args.data)
		else:
			Handler.game_dir = find_game_dir(game_dir_candidates())
	if Handler.game_dir:
		Handler.game_dir = os.path.abspath(Handler.game_dir)
		Handler.game_files = collect_game_files(Handler.game_dir)
		print("Game files from %s (%d files); saved games are written there." % (Handler.game_dir, len(Handler.game_files)))
	else:
		print("No local game files: the page will ask for them.")
	print("Serving %s\nOpen http://127.0.0.1:%d/" % (WEBROOT, args.port))
	http.server.ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
	main()
