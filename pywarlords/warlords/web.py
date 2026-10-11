"""Browser support (pygbag / CPython on WebAssembly).

The game files cannot be published with the page, so the player picks their own copy once: the
game folder, a .zip of it, or the individual files. The browser keeps them (IndexedDB) for the next
visit, together with saved games. Nothing is uploaded anywhere: the files go from the player's disk
into the page's memory only.

When the page is served by web/serve.py with a local game folder, the files come from that server
(local-game/) instead and saved games are written back into the folder.

On the desktop every function here is a no-op.
"""
import asyncio
import json
import os
import sys
import zipfile

WEB = sys.platform == 'emscripten'
GAME_DIR = '/tmp/warlords'

try:
	if WEB:
		import platform as _platform      # pygbag replaces it with the browser bridge
		window = _platform.window
	else:
		window = None
except Exception:                       # pragma: no cover
	window = None


JS = r"""
(function () {
if (window.wl) return;
const wl = window.wl = { state: 'init', msg: '' };
const DB = 'warlords-files', STORE = 'files', ROOT = '%(root)s';
const KEEP = /\.(exe|map|pck|sjh|rjk|sav)$/i;

function idb() {
	return new Promise((res, rej) => {
		const r = indexedDB.open(DB, 1);
		r.onupgradeneeded = () => r.result.createObjectStore(STORE);
		r.onsuccess = () => res(r.result);
		r.onerror = () => rej(r.error);
	});
}
async function idbAll() {
	const db = await idb();
	return new Promise((res, rej) => {
		const out = {}, rq = db.transaction(STORE, 'readonly').objectStore(STORE).openCursor();
		rq.onsuccess = () => { const c = rq.result; if (c) { out[c.key] = c.value; c.continue(); } else res(out); };
		rq.onerror = () => rej(rq.error);
	});
}
async function idbPut(files, clear) {
	const db = await idb();
	return new Promise((res, rej) => {
		const tx = db.transaction(STORE, 'readwrite'), st = tx.objectStore(STORE);
		if (clear) st.clear();
		for (const k in files) st.put(files[k], k);
		tx.oncomplete = () => res();
		tx.onerror = () => rej(tx.error);
	});
}
function mkdir(p) { try { window.python.FS.mkdir(p); } catch (e) {} }
function fsWrite(files) {
	const FS = window.python.FS;
	mkdir(ROOT); mkdir(ROOT + '/PICTS');
	for (const k in files) FS.writeFile(ROOT + '/' + k, files[k]);
}

// ---- the overlay ---------------------------------------------------------------------------
const css = `
#wl-ov { position: fixed; inset: 0; display: none; align-items: center; justify-content: center;
	background: rgba(0,0,0,.82); z-index: 1000; font: 15px/1.45 system-ui, sans-serif; color: #222; }
#wl-box { background: #aaa; border: 3px solid; border-color: #eee #555 #555 #eee; padding: 22px 26px;
	max-width: 520px; margin: 16px; box-shadow: 0 0 0 2px #000; }
#wl-box h1 { margin: 0 0 10px; font: bold 22px/1.2 Georgia, serif; letter-spacing: .5px; }
#wl-box p { margin: 0 0 12px; }
#wl-box code { background: #ccc; padding: 0 3px; }
#wl-box .row { display: flex; gap: 10px; flex-wrap: wrap; margin: 16px 0 6px; }
#wl-box button { font: bold 15px system-ui, sans-serif; padding: 9px 14px; cursor: pointer; background: #ccc;
	border: 2px solid; border-color: #fff #444 #444 #fff; }
#wl-box button:active { border-color: #444 #fff #fff #444; }
#wl-msg { color: #800; min-height: 1.4em; font-weight: 600; }
#wl-box small { color: #333; }`;
const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
const ov = document.createElement('div'); ov.id = 'wl-ov';
ov.innerHTML = `<div id="wl-box">
<h1>Warlords</h1>
<p>This page runs <b>Warlords</b> (SSG, 1990) in your browser, but it needs <b>your copy of the original
game</b>: <code>WARLORDS.EXE</code>, <code>ILLURIA.MAP</code> and the <code>PICTS</code> folder
(for example from GOG's <i>Warlords 1 + 2 Deluxe</i>).</p>
<p>Choose the game folder, or a <code>.zip</code> of it. The files stay in this browser and are not
uploaded anywhere.</p>
<div class="row"><button id="wl-dir">Choose game folder</button><button id="wl-zip">Choose .zip or files</button></div>
<div id="wl-msg"></div>
<small>On a Mac the GOG game is inside <code>Warlords.app/Contents/Resources/game</code>; use
"Show Package Contents" in Finder and zip the <code>game</code> folder.</small>
</div>`;
document.body.appendChild(ov);
const inDir = document.createElement('input');
inDir.type = 'file'; inDir.webkitdirectory = true; inDir.multiple = true; inDir.hidden = true;
const inZip = document.createElement('input');
inZip.type = 'file'; inZip.multiple = true; inZip.hidden = true;
inZip.accept = '.zip,.exe,.map,.pck,.sjh,.rjk,.sav';
document.body.appendChild(inDir); document.body.appendChild(inZip);
document.getElementById('wl-dir').onclick = () => inDir.click();
document.getElementById('wl-zip').onclick = () => inZip.click();

function show(msg) {
	document.getElementById('wl-msg').textContent = msg || '';
	ov.style.display = 'flex';
	wl.state = 'need';
}
wl.show = show;

async function take(list) {
	const files = {}, depth = {};
	for (const f of list) {
		const rel = (f.webkitRelativePath || f.name).replace(/\\/g, '/');
		const parts = rel.split('/');
		const base = parts.pop();
		if (/\.zip$/i.test(base)) {
			files['__zip__'] = new Uint8Array(await f.arrayBuffer()); depth['__zip__'] = 0; continue;
		}
		if (!KEEP.test(base)) continue;
		const parent = parts.length ? parts[parts.length - 1].toUpperCase() : '';
		const key = /\.pck$/i.test(base) || parent === 'PICTS' ? 'PICTS/' + base : base;
		const d = parts.length;
		if (key in files && depth[key] <= d) continue;
		files[key] = new Uint8Array(await f.arrayBuffer()); depth[key] = d;
	}
	const names = Object.keys(files).map(k => k.toUpperCase());
	if (!('__zip__' in files) && !names.includes('WARLORDS.EXE')) {
		show('WARLORDS.EXE was not found in what you picked.');
		return;
	}
	ov.style.display = 'none';
	wl.msg = 'Loading...';
	try { await idbPut(files, true); } catch (e) { console.warn('warlords: cannot store files', e); }
	fsWrite(files);
	wl.state = 'ready';
}
inDir.onchange = () => take(inDir.files);
inZip.onchange = () => take(inZip.files);

wl.persist = async function (path, key) {
	try {
		const data = window.python.FS.readFile(path);
		if (wl.local) {
			// served by web/serve.py: the saved game goes back into the game folder
			const r = await fetch(LOCAL + encodeURIComponent(key), { method: 'PUT', body: data });
			if (!r.ok) console.warn('warlords: cannot save', key, r.status);
			return;
		}
		const o = {}; o[key] = data;
		await idbPut(o, false);
	} catch (e) { console.warn('warlords: cannot store', path, e); }
};
wl.forget = async function (msg) {
	wl.local = false;
	try { await idbPut({}, true); } catch (e) {}
	show(msg);
};

// web/serve.py --data offers the game folder of the machine it runs on under local-game/
const LOCAL = 'local-game/';
async function fromServer() {
	try {
		const r = await fetch(LOCAL + 'index.json', { cache: 'no-store' });
		if (!r.ok) return false;
		const idx = await r.json();
		if (!idx.files || !idx.files.length) return false;
		const files = {};
		for (const k of idx.files) {
			const f = await fetch(LOCAL + k.split('/').map(encodeURIComponent).join('/'), { cache: 'no-store' });
			if (!f.ok) return false;
			files[k] = new Uint8Array(await f.arrayBuffer());
		}
		fsWrite(files);
		wl.local = true;
		return true;
	} catch (e) { return false; }
}

(async function () {
	if (/[?&]reset\b/.test(location.search)) { try { await idbPut({}, true); } catch (e) {} }
	if (await fromServer()) { wl.state = 'ready'; return; }
	let files = {};
	try { files = await idbAll(); } catch (e) { console.warn('warlords: no IndexedDB', e); }
	if (Object.keys(files).length) { fsWrite(files); wl.state = 'ready'; }
	else show('');
})();
})();
"""


def _js(code):
	return window.eval(code)


def _extract_zip(path, dest):
	"""Extract the game files of a zip (any folder layout) into dest/ and dest/PICTS/."""
	exts = ('.exe', '.map', '.pck', '.sjh', '.rjk', '.sav')
	best = {}
	with zipfile.ZipFile(path) as z:
		for info in z.infolist():
			if info.is_dir():
				continue
			parts = info.filename.replace('\\', '/').split('/')
			base = parts[-1]
			if not base.lower().endswith(exts) or base.startswith('._') or '__MACOSX' in parts:
				continue
			parent = parts[-2].upper() if len(parts) > 1 else ''
			key = 'PICTS/' + base if (base.lower().endswith('.pck') or parent == 'PICTS') else base
			d = len(parts)
			if key.upper() in best and best[key.upper()][0] <= d:
				continue
			best[key.upper()] = (d, key, info)
		os.makedirs(os.path.join(dest, 'PICTS'), exist_ok=True)
		for d, key, info in best.values():
			out = os.path.join(dest, key)
			if os.path.exists(out):           # a saved game restored from the browser wins
				continue
			with z.open(info) as src, open(out, 'wb') as dst:
				dst.write(src.read())


async def obtain_game_dir(check):
	"""Wait until the player has given us the game files; returns the folder.
	check(folder) returns an error message or None."""
	_js(JS % {'root': GAME_DIR})
	while True:
		while str(window.wl.state) != 'ready':
			await asyncio.sleep(0.1)
		z = os.path.join(GAME_DIR, '__zip__')
		err = None
		if os.path.exists(z):
			try:
				_extract_zip(z, GAME_DIR)
			except Exception as e:
				err = "That .zip could not be read (%s)." % e
		if err is None:
			err = check(GAME_DIR)
		if err is None:
			return GAME_DIR
		window.wl.state = 'need'
		_js("window.wl.forget(%s)" % json.dumps(err))


def audio_unlocked():
	"""False while the browser still waits for a click or key before it plays sound."""
	if not WEB or window is None:
		return True
	try:
		# browsers start audio only after the page got a click or key (user activation)
		_js("window.wl.active = String(navigator.userActivation ? navigator.userActivation.hasBeenActive : true)")
		return str(window.wl.active).lower() == 'true'
	except Exception:
		return True


def report(key, value):
	"""Expose a bit of game state to the page (window.wl.<key>), for automated browser tests."""
	if not WEB or window is None:
		return
	try:
		_js("window.wl[%s] = %s" % (json.dumps(key), json.dumps(value)))
	except Exception:
		pass


def persist_file(path):
	"""Keep a file written by the game (a saved game) in the browser."""
	if not WEB or window is None:
		return
	try:
		_js("window.wl.persist(%s, %s)" % (json.dumps(path), json.dumps(os.path.basename(path))))
	except Exception:
		pass
