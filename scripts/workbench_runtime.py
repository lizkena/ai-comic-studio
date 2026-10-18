"""Launcher diagnostics. Reads metadata only, without importing the application."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import runtime

parser = argparse.ArgumentParser()
parser.add_argument('--fingerprint', action='store_true')
parser.add_argument('--data', type=Path, default=Path(os.environ.get('COMIC_STUDIO_DATA', ROOT/'data')))
args = parser.parse_args()
if args.fingerprint:
    print(runtime.LOADED_FINGERPRINT)
else:
    print(json.dumps(runtime.activity(args.data.resolve())))
