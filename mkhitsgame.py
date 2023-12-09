#!/usr/bin/env python3

from __future__ import annotations

import os
import os.path
import subprocess
import sys

from typing import NamedTuple

def metaflac_get_tags(fname: str) -> Dict[str, str]:
    """
    Return the metadata tags (Vorbis comments) from the file. If a tag is
    repeated, only the last value is kept.
    """
    out = subprocess.check_output(
        ["metaflac", "--export-tags-to=-", fname],
        encoding="utf-8",
    )
    tags = [line.split("=", maxsplit=1) for line in out.splitlines()]
    return {k.upper(): v for k, v in tags}


class Track(NamedTuple):
    fname: str
    title: str
    artist: str
    year: int

    @staticmethod
    def load(fname: str) -> Track:
        tags = metaflac_get_tags(fname)
        title = tags.get("TITLE")
        artist = tags.get("ARTIST")
        date = tags.get("ORIGINALDATE", tags.get("DATE"))
        if title is None:
            print(f"{fname}: No TITLE tag present.")
            sys.exit(1)
        if artist is None:
            print(f"{fname}: No ARTIST tag present.")
            sys.exit(1)
        if date is None:
            print(f"{fname}: No ORIGINALDATE or DATE tag present.")
            sys.exit(1)
        return Track(fname, title, artist, int(date[0:4]))


def main() -> None:
    os.makedirs("out", exist_ok=True)
    track_dir = "tracks"
    for fname in os.listdir(track_dir):
        fname_full = os.path.join(track_dir, fname)
        track = Track.load(fname_full)
        print(track)


if __name__ == "__main__":
    main()
