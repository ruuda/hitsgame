#!/usr/bin/env python3

from __future__ import annotations

import html
import os
import os.path
import shutil
import subprocess
import sys
import tomllib

import qrcode
from qrcode.image.svg import SvgPathImage

from typing import Dict, Iterable, List, Literal, NamedTuple, Tuple

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

    def qr_svg(self) -> Tuple[str, int]:
        """
        Render a QR code for the URL as SVG path, return also the side length
        (in SVG units, which by convention we map to mm).
        """
        from qrcode.compat.etree import ET  # type: ignore
        # A box size of 10 means that every "pixel" in the code is 1mm, but we
        # don't know how many pixels wide and tall the code is.
        qr = qrcode.make(self.url, image_factory=SvgPathImage, box_size=10)
        return ET.tostring(qr.path).decode("ascii"), qr.pixel_size / qr.box_size


class Config(NamedTuple):
    url_prefix: str
    font: str

    @staticmethod
    def load(fname: str) -> Config:
        with open(fname, "rb") as f:
            toml = tomllib.load(f)
            return Config(**toml)


def line_break_text(s: str) -> List[str]:
    """
    Line break the artist and title so they (hopefully) fit on a card. This is a
    hack based on string lengths, but it's good enough for most cases.
    """
    if len(s) < 28:
        return [s]

    words = s.split(" ")
    char_count = sum(len(word) for word in words)

    # The starting situation is everything on the first line. We'll try out
    # every possible line break and pick the one with the most even distribution
    # (by characters in the string, not true text width).
    top, bot = " ".join(words), ""
    diff = char_count

    # Try line-breaking between every word.
    for i in range(1, len(words) - 1):
        w1, w2 = words[:i], words[i:]
        t, b = " ".join(w1), " ".join(w2)
        d = abs(len(t) - len(b))
        if d < diff:
            top, bot, diff = t, b, d

    return [top, bot]


def render_text_svg(x_mm: float, y_mm: float, s: str, class_: str) -> Iterable[str]:
    """
    Render the artist or title, broken across lines if needed.
    """
    lines = line_break_text(s)
    line_height_mm = 7
    h_mm = line_height_mm * len(lines)

    for i, line in enumerate(lines):
        dy_mm = line_height_mm * (1 + i) - h_mm / 2
        yield (
            f'<text x="{x_mm}" y="{y_mm + dy_mm}" text-anchor="middle" '
            f'class="{class_}">{html.escape(line)}</text>'
        )


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

    def render_svg(self, config: Config, mode: Literal["qr"] | Literal["title"]) -> str:
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
            f"""
            <style>
            text {{ font-family: {config.font!r}; }}
            .year {{ font-size: 18px; font-weight: 900; }}
            .title, .artist {{ font-size: 6px; font-weight: 400; }}
            .title {{ font-style: italic; }}
            </style>
            """
        )
        parts.append(
            f'<rect x="{hmargin_mm}" y="{vmargin_mm}" '
            f'width="{tw_mm}" height="{th_mm}" '
            'fill="transparent" stroke="black" stroke-width="0.1" stroke-linejoin="miter"/>'
        )
        for ix in range(1, self.width):
            x_mm = hmargin_mm + ix * side_mm
            parts.append(
                f'<line x1="{x_mm}" y1="{vmargin_mm}" '
                f'x2="{x_mm}" y2="{vmargin_mm + th_mm}" '
                'stroke="black" stroke-width="0.1" />'
            )
        for iy in range(1, self.height):
            y_mm = vmargin_mm + iy * side_mm
            parts.append(
                f'<line x1="{hmargin_mm}" y1="{y_mm}" '
                f'x2="{hmargin_mm + tw_mm}" y2="{y_mm}" '
                'stroke="black" stroke-width="0.1" />'
            )

        for i, track in enumerate(self.cells):
            if mode == "qr":
                ix = i % self.width
                iy = i // self.width
                qr_path, qr_mm = track.qr_svg()
                # I'm lazy so we center the QR codes, we don't resize them. If the
                # urls get longer, then the QR codes will cover a larger area of the
                # cards.
                x_mm = hmargin_mm + ix * side_mm + (side_mm - qr_mm) / 2
                y_mm = vmargin_mm + iy * side_mm + (side_mm - qr_mm) / 2
                parts.append(f'<g transform="translate({x_mm}, {y_mm})">')
                parts.append(qr_path)
                parts.append(f'</g>')

            if mode == "title":
                # Note, we mirror over the x-axis, to match the QR codes when
                # printed double-sided.
                ix = self.width - 1 - (i % self.width)
                iy = i // self.width
                x_mm = hmargin_mm + (ix + 0.5) * side_mm
                y_mm = vmargin_mm + (iy + 0.5) * side_mm
                parts.append(
                    f'<text x="{x_mm}" y="{y_mm + 7}" text-anchor="middle" '
                    f'class="year">{track.year}</text>'
                )
                for part in render_text_svg(x_mm, y_mm - 19, track.artist, "artist"):
                    parts.append(part)
                for part in render_text_svg(x_mm, y_mm + 18, track.title, "title"):
                    parts.append(part)

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

    with open("front.svg", "w", encoding="utf-8") as f:
        f.write(tables[0].render_svg(config, "qr"))
    with open("back.svg", "w", encoding="utf-8") as f:
        f.write(tables[0].render_svg(config, "title"))


if __name__ == "__main__":
    main()
