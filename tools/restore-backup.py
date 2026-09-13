"""Verify a dashboard ZIP and restore into a NEW state directory, never overwrite live data."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backup import restore_archive

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('zipfile')
parser.add_argument('new_state_directory')
args = parser.parse_args()
result = restore_archive(args.zipfile, args.new_state_directory)
print(f"Verified and restored {result['captures']} captures. Stop the service before changing ASTRO_STATE.")
