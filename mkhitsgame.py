#!/usr/bin/env python3

from __future__ import annotations

import os
import os.path
import shutil
import subprocess
import sys
import tomllib

import qrcode
from qrcode.image.svg import SvgPathImage

from typing import Dict, NamedTuple, Tuple

def metaflac_get_tags(fname: str) -> Tuple[str, Dict[str, str]]:
    """
    Return the metadata tags (Vorbis comments) from the file. If a tag is
    repeated, only the last value is kept. Returns the audio data md5sum as
    well.
    """
    out = subprocess.check_output(
        ["metaflac", "--show-md5sum", "--export-tags-to=-", fname],
        encoding="utf-8",
    )
    lines = out.splitlines()
    md5sum = lines[0]
    tags = [line.split("=", maxsplit=1) for line in lines[1:]]
    return md5sum, {k.upper(): v for k, v in tags}


class Track(NamedTuple):
    fname: str
    title: str
    artist: str
    year: int
    md5sum: str

    @staticmethod
    def load(fname: str) -> Track:
        """
        Create a track from an input filename.
        """
        md5sum, tags = metaflac_get_tags(fname)
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
        return Track(fname, title, artist, int(date[0:4]), md5sum)

    def out_fname(self) -> str:
        return self.md5sum + ".flac"

    def copy_to_out(self) -> None:
        """
        Copy the file into the output directory with metadata stripped, under
        an unpredictable (but reproducible) name based on the audio md5sum.
        """
        shutil.copy(self.fname, "out/tmp.flac");
        subprocess.check_call(["metaflac", "--remove-all", "out/tmp.flac"])
        os.rename("out/tmp.flac", os.path.join("out", self.out_fname()))

    def url(self, config: Config) -> str:
        return config.url_prefix + self.out_fname()

    def qr_svg(self, config: Config) -> str:
        from qrcode.compat.etree import ET  # type: ignore
        url = self.url(config)
        qr = qrcode.make(self.url(config), image_factory=SvgPathImage)
        return qr.to_string()


class Config(NamedTuple):
    url_prefix: str

    @staticmethod
    def load(fname: str) -> Config:
        with open(fname, "rb") as f:
            toml = tomllib.load(f)
            return Config(**toml)


def main() -> None:
    config = Config.load("mkhitsgame.toml")
    os.makedirs("out", exist_ok=True)
    track_dir = "tracks"
    for fname in os.listdir(track_dir):
        fname_full = os.path.join(track_dir, fname)
        track = Track.load(fname_full)
        track.copy_to_out()
        print(track)
        qr = track.qr_svg(config)
        with open("out/x.svg", "wb") as f:
            f.write(qr)


if __name__ == "__main__":
    main()
