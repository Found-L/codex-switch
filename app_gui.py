import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from codex_switch.gui import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--self-test", type=Path, metavar="REPORT", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_test:
        from codex_switch.gui import self_test
        raise SystemExit(self_test(args.self_test))
    else:
        run(args.codex_home)
