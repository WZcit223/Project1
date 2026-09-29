"""Regenerate the synthetic, M5-shaped test fixture in tests/fixtures/m5_like/.

Usage: uv run python scripts/make_m5_fixture.py [--output DIR]
"""

import argparse
from pathlib import Path

from industrial_ai_warehouse.adapters.m5.fixture import write_m5_fixture

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "m5_like"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_m5_fixture(args.output)
    print(f"wrote synthetic M5-shaped fixture to {args.output}")


if __name__ == "__main__":
    main()
