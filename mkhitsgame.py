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

from typing import Dict, List, NamedTuple, Tuple

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
    url: str

    @staticmethod
    def load(config: Config, fname: str) -> Track:
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

        url = config.url_prefix + md5sum + ".flac"

        return Track(fname, title, artist, int(date[0:4]), md5sum, url)

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

    def qr_svg(self) -> str:
        from qrcode.compat.etree import ET  # type: ignore
        qr = qrcode.make(self.url, image_factory=SvgPathImage)
        return ET.tostring(qr.path).decode("ascii")


class Config(NamedTuple):
    url_prefix: str

    @staticmethod
    def load(fname: str) -> Config:
        with open(fname, "rb") as f:
            toml = tomllib.load(f)
            return Config(**toml)


class Table(NamedTuple):
    """
    A table of cards laid out on two-sided paper.
    """
    cells: List[Track]

    # Hitster cards are 65mm wide, so on a 210mm wide A4 paper, we can fit
    # 3 columns and still have 7mm margin on both sides. That may be a bit
    # tight but either way, let's do 3 columns.
    width: int = 3

    # In the 297mm A4 paper, if we put 4 rows of 65mm that leaves 37mm of
    # margin, about 20mm top and bottom.
    height: int = 4

    @staticmethod
    def new() -> Table:
        return Table(cells=[])

    def append(self, track: Track) -> None:
        self.cells.append(track)

    def is_empty(self) -> bool:
        return len(self.cells) == 0

    def is_full(self) -> bool:
        return len(self.cells) >= self.width * self.height

    def front_svg(self) -> str:
        """
        Render the front of the page as svg. The units are in millimeters.
        """
        # Size of the page.
        w_mm = 210
        h_mm = 297
        # Size of the cards / table cells.
        side_mm = 65

        tw_mm = side_mm * self.width
        th_mm = side_mm * self.height
        hmargin_mm = (w_mm - tw_mm) / 2
        vmargin_mm = (h_mm - th_mm) / 2

        parts: List[str] = []
        parts.append(
            '<svg version="1.1" width="210" height="297" '
            'viewBox="0 0 210 297" '
            'xmlns="http://www.w3.org/2000/svg">'
        )
        parts.append(
            f'<rect x="{hmargin_mm}" y="{vmargin_mm}" '
            f'width="{tw_mm}" height="{th_mm}" '
            'fill="transparent" stroke="black" stroke-width="1" stroke-linejoin="miter"/>'
        )
        for ix in range(1, self.width):
            x_mm = hmargin_mm + ix * side_mm
            parts.append(
                f'<line x1="{x_mm}" y1="{vmargin_mm}" '
                f'x2="{x_mm}" y2="{vmargin_mm + th_mm}" '
                'stroke="black" stroke-width="1" />'
            )
        for iy in range(1, self.height):
            y_mm = vmargin_mm + iy * side_mm
            parts.append(
                f'<line x1="{hmargin_mm}" y1="{y_mm}" '
                f'x2="{hmargin_mm + tw_mm}" y2="{y_mm}" '
                'stroke="black" stroke-width="1" />'
            )

        parts.append("</svg>")

        return "\n".join(parts)


def main() -> None:
    config = Config.load("mkhitsgame.toml")
    os.makedirs("out", exist_ok=True)
    track_dir = "tracks"

    table = Table.new()
    tables: List[Table] = []
    tracks: List[Track] = []

    for fname in os.listdir(track_dir):
        fname_full = os.path.join(track_dir, fname)
        track = Track.load(config, fname_full)
        track.copy_to_out()
        tracks.append(track)

    tracks.sort()
    for track in tracks:
        table.append(track)

        if table.is_full():
            tables.append(table)
            table = Table.new()

    # Append the final table, which may not be full.
    if not table.is_empty():
        tables.append(table)

    with open("cards.svg", "w", encoding="utf-8") as f:
        f.write(tables[0].front_svg())


if __name__ == "__main__":
    main()
