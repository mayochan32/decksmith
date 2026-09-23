"""Read the version shipped alongside this installed skill."""
from pathlib import Path
import re


def read_version():
    value = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise ValueError("Invalid DeckSmith VERSION: " + value)
    return value


if __name__ == "__main__":
    print("DeckSmith " + read_version())
