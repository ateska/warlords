# Warlords in the browser

The same Python code runs in the browser with [pygbag](https://pygame-web.github.io)
(CPython and pygame compiled to WebAssembly). Nothing is translated: `web/main.py` starts the
normal game.

## Game files

The page does not contain any game files. Served by `web/serve.py` with a local game folder, it
loads them from that server (see *Running it locally*). Otherwise, on the first visit, the player
chooses their own copy of
Warlords: the game folder, a `.zip` of it, or the individual files (`WARLORDS.EXE`, `ILLURIA.MAP`,
`PICTS/*.PCK`, optionally the `*.SJH` sounds and `WAR?.SAV` saved games). The files are read
locally by the page and kept in the browser's IndexedDB for the next visit. Nothing is uploaded.
Saved games are kept in the browser too. Open the page with `?reset` to forget the stored files.

On macOS the GOG game is inside `Warlords.app/Contents/Resources/game` (Finder: *Show Package
Contents*). The browser's folder picker cannot enter an `.app` bundle, so zip the `game` folder and
choose the zip.

## Build

```
pip install pygbag
python3 web/build.py
```

The result is `build/web/` (`index.html`, `warlords.apk`, `favicon.png`, about 80 kB). It is a
static site that any web server can host.

## Running it locally

```
python3 web/serve.py --data /path/to/warlords     # then open http://127.0.0.1:8001/
```

`serve.py` works like the desktop launcher: it takes the game folder from `--data`, or finds it the
same way (`$WARLORDS_DATA`, the current folder, `../warlords`, the GOG installation on macOS). The
page then loads the game files from the server instead of asking for them, and saved games
(`WAR1.SAV` ... `WAR8.SAV`) are written back into that folder, where the desktop version and DOS
Warlords find them too. `--upload` turns this off, so the page asks for the files as it does on a
public site. Other options: a port number (default 8001); `build.py --serve PORT` builds and then
starts `serve.py` (passing `--data` and `--upload` on).

The game files are offered under `/local-game/` only, the server only listens on `127.0.0.1`, and
the only files it accepts from the page are the saved games.

Open the page as `127.0.0.1`, not `localhost`: on a page whose host name is `localhost` the pygbag
runtime switches to its developer mode and asks for pygame at `http://localhost:8000/archives/repo/`
(pygbag's own test server), whatever port the page uses. A plain `python3 -m http.server` works
too when opened as `127.0.0.1`, but then the page asks for the game files.

The CPython/pygame WebAssembly runtime (about 10 MB, cached by the browser) is loaded from the
pygbag CDN (`--cdn`, default `https://pygame-web.github.io/archives/0.9/`).

## Publishing

`build/web/` needs no server-side code. To publish it on GitHub Pages, copy its three files into a
folder of the branch Pages is served from, for example `play/` in this repository's `web` branch:

```
git worktree add ../warlords-web web
mkdir -p ../warlords-web/play && cp build/web/index.html build/web/warlords.apk build/web/favicon.png ../warlords-web/play/
cd ../warlords-web && git add play && git commit -m "Warlords in the browser" && git push
```

The game is then at `https://<user>.github.io/<repository>/play/`.

## How it fits together

* The game is written like the original: rules code calls modal dialogs that run their own event
  loops. In a browser every loop must give control back each frame, so all functions that wait for
  the player are `async` and `Screen.tick()` ends a frame with `await asyncio.sleep(0)`. On the
  desktop `asyncio.run()` drives the same code.
* `warlords/web.py` first asks the server for `local-game/index.json` (only `serve.py` answers it);
  otherwise it shows the file chooser (a small HTML overlay), stores and restores the files, and
  unpacks a zip into `/tmp/warlords`.
* `web/warlords.tmpl` is pygbag's default page template with a black background, sharp pixel
  scaling, and the game's keys (F1–F10, Tab, Alt+letter) kept away from the browser.
* No numpy: pictures are decoded in pure Python and drawn as 8 bit palette surfaces.
* For automated browser tests the page exposes a little state in `window.wl` (`state`, `human_turn`,
  `sound`, `played`), and `?bench` runs 20 computer-only turns without drawing and reports the time in
  `window.wl.bench`.

Computer turns run about two times slower than native CPython, which is still well under a second
per turn. Games are deterministic across platforms: the same seed gives the same game in the
browser and on the desktop.

## Known limits

* The menus need the right mouse button (hold it), as in the original; there is no touch control.
* `Ctrl+Q` and `Ctrl+W` may close the browser tab instead of reaching the game; use the menu.
  Quitting the game returns to the title screen.
* The browser shows a confirmation when you leave or reload the page (pygbag's default).
