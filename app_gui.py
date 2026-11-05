import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from codex_switch.gui import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-home", type=Path)
    args = parser.parse_args()
    run(args.codex_home)
