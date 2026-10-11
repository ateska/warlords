"""Build the browser version with pygbag.

	pip install pygbag
	python3 web/build.py            # -> build/web/index.html + warlords.apk

Serve build/web/ with any static web server (GitHub Pages works) and open index.html.
Options:
	--cdn URL     where the pygbag runtime (CPython/pygame WebAssembly) is loaded from
	              (default: the official pygbag CDN, must end with the version folder, e.g. .../0.9/)
	--serve PORT  serve build/web after building (web/serve.py; --data and --upload are passed on)
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument('--cdn', default='https://pygame-web.github.io/archives/0.9/')
	ap.add_argument('--serve', type=int, default=0)
	ap.add_argument('--data', help="(with --serve) folder with the original game files")
	ap.add_argument('--upload', action='store_true', help="(with --serve) do not offer local game files")
	args = ap.parse_args()

	stage = os.path.join(ROOT, 'build', 'warlords')
	out = os.path.join(ROOT, 'build', 'web')
	shutil.rmtree(stage, ignore_errors=True)
	shutil.copytree(os.path.join(ROOT, 'warlords'), os.path.join(stage, 'warlords'),
		ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
	shutil.copy(os.path.join(HERE, 'main.py'), stage)
	shutil.copy(os.path.join(HERE, 'favicon.png'), stage)
	cmd = [sys.executable, '-m', 'pygbag', '--build', '--title', 'Warlords', '--app_name', 'warlords',
		'--cdn', args.cdn, '--template', os.path.join(HERE, 'warlords.tmpl'),
		'--icon', os.path.join(HERE, 'favicon.png'), '--ume_block', '0', '--width', '1280', '--height', '800', stage]
	print(' '.join(cmd))
	subprocess.check_call(cmd, cwd=stage)
	shutil.rmtree(out, ignore_errors=True)
	shutil.copytree(os.path.join(stage, 'build', 'web'), out)
	print("\nbuilt", out)
	for f in sorted(os.listdir(out)):
		print("  %-20s %8d" % (f, os.path.getsize(os.path.join(out, f))))
	if args.serve:
		cmd = [sys.executable, os.path.join(HERE, 'serve.py'), str(args.serve)]
		if args.data:
			cmd += ['--data', args.data]
		if args.upload:
			cmd.append('--upload')
		subprocess.call(cmd)


if __name__ == '__main__':
	main()
