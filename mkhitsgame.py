#!/usr/bin/env python3

# Hitsgame -- Build cards for a music game
# Copyright 2023 Ruud van Asseldonk

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.

from __future__ import annotations

import hashlib
import html
import os
import os.path
import shutil
import subprocess
import sys
import tomllib

import qrcode  # type: ignore

from typing import Dict, Iterable, List, Literal, NamedTuple, Tuple
from collections import Counter

from qrcode.image.svg import SvgPathImage  # type: ignore

try:
    from mutagen import File
    from mutagen.id3 import ID3NoHeaderError
except ImportError:
    print("Error: mutagen library not found. Install with: pip install mutagen")
    sys.exit(1)

class Track(NamedTuple):
    year: int
    fname: str
    title: str
    artist: str
    md5sum: str
    url: str

    @staticmethod
    def load_from_file(config: Config, file_path: str) -> Track | None:
        """
        Create a track from a song file in original_songs folder.
        """
        try:
            # Extract ID3 tags
            audio_file = File(file_path)
            if audio_file is None:
                print(f"Warning: Unsupported file format: {file_path}")
                return None
            
            # Get metadata
            title = ""
            artist = ""
            year = ""
            
            if hasattr(audio_file, 'tags') and audio_file.tags:
                # For MP3 files with ID3 tags
                title = str(audio_file.tags.get('TIT2', [''])[0]) if audio_file.tags.get('TIT2') else ''
                artist = str(audio_file.tags.get('TPE1', [''])[0]) if audio_file.tags.get('TPE1') else ''
                
                # Prefer ORIGINALDATE, then TDRC, then TYER
                year_tag = audio_file.tags.get('TDOR', [''])[0] if audio_file.tags.get('TDOR') else ''
                if not year_tag:
                    year_tag = audio_file.tags.get('TDRC', [''])[0] if audio_file.tags.get('TDRC') else ''
                if not year_tag:
                    year_tag = audio_file.tags.get('TYER', [''])[0] if audio_file.tags.get('TYER') else ''
                year = str(year_tag)[:4] if year_tag else ''
            else:
                # For other formats, try generic tags
                title = str(audio_file.get('TITLE', [''])[0]) if audio_file.get('TITLE') else ''
                artist = str(audio_file.get('ARTIST', [''])[0]) if audio_file.get('ARTIST') else ''
                
                # Prefer ORIGINALDATE, then DATE, then YEAR
                year_tag = audio_file.get('ORIGINALDATE', [''])[0] if audio_file.get('ORIGINALDATE') else ''
                if not year_tag:
                    year_tag = audio_file.get('DATE', [''])[0] if audio_file.get('DATE') else ''
                if not year_tag:
                    year_tag = audio_file.get('YEAR', [''])[0] if audio_file.get('YEAR') else ''
                year = str(year_tag)[:4] if year_tag else ''
            
            # Validate required fields
            if not title or not artist or not year:
                print(f"Warning: Missing required tags in {file_path}")
                print(f"  Title: '{title}', Artist: '{artist}', Year: '{year}'")
                return None
            
            # Create MD5 hash from year, artist, title
            hash_input = f"{year}_{artist}_{title}"
            md5sum = hashlib.md5(hash_input.encode('utf-8')).hexdigest()
            
            # Get file extension
            _, ext = os.path.splitext(file_path)
            
            # Create URL (MP4 will be created during encoding step)
            url = config.url_prefix + md5sum + ".mp4"
            
            return Track(
                year=int(year) if year.isdigit() else 0,
                fname=file_path,  # Keep original file path for encoding
                title=title,
                artist=artist,
                md5sum=md5sum,
                url=url
            )
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return None

    def out_fname(self) -> str:
        return self.md5sum + ".mp4"

    def encode_to_out(self, config: Config) -> None:
        """
        Encode the input audio file to an mp4 file in the output directory, under
        a hash-based filename. The resulting file has all metadata removed and is
        converted to mono AAC format for the game.
        """
        out_fname = os.path.join(config.songs_dir, self.out_fname())
        
        if os.path.isfile(out_fname):
            return
        
        print(f"Encoding: {os.path.basename(self.fname)} -> {self.out_fname()}")
        
        subprocess.check_call([
            "ffmpeg",
            "-i", self.fname,
            # Copy the audio stream, and no other stream (no cover art).
            "-map", "0:a",
            # By default ffmpeg copies metadata from the input file (file 0).
            # Disable this by copying from the non-existing file -1 instead.
            "-map_metadata", "-1",
            # Really disable metadata writing, including the encoder tag.
            "-write_xing", "0",
            "-id3v2_version", "0",
            # Downmix stereo to mono (audio channels = 1). When we play the game
            # we listen on a phone speaker or bluetooth speaker anyway.
            "-ac", "1",
            # Encode as AAC at 128kbps.
            "-b:a", "128k",
            "-c:a", "aac",
            "-to", "60", # first 60 seconds
            out_fname,
        ])

    def qr_svg(self) -> Tuple[str, int]:
        """
        Render a QR code for the URL as SVG path, return also the side length
        (in SVG units, which by convention we map to mm).
        """
        from qrcode.compat.etree import ET  # type: ignore

        # A box size of 10 means that every "pixel" in the code is 1mm, but we
        # don't know how many pixels wide and tall the code is, so return that
        # too, the "pixel size". Note, it is independent of the specified box
        # size, we always have to divide by 10.
        qr = qrcode.make(self.url, image_factory=SvgPathImage, box_size=8)
        return ET.tostring(qr.path).decode("ascii"), qr.pixel_size / 10


class Config(NamedTuple):
    url_prefix: str
    font: str
    songs_dir: str

    # Whether to include a grid in the output. This is good for inspecting the
    # output on a computer, but for print, unless you want to use the grid as
    # a guide for scissors to cut, you probably want to enable crop marks and
    # disable the grid, so a slight misalignment when cutting does not result in
    # a line near the edge of the card.
    grid: bool

    # Whether to include crop marks in the output that indicate where to cut.
    crop_marks: bool

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
    if len(s) < 24:
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
    line_height_mm = 6
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

    def render_svg(
        self, config: Config, mode: Literal["qr"] | Literal["title"], page_footer: str
    ) -> str:
        """
        Render the front of the page as svg. The units are in millimeters.
        """
        # Size of the page.
        w_mm = 210
        h_mm = 297
        # Size of the cards / table cells. In the Hitster game I have, the cards
        # have a side length of 65mm. But then fitting the table on A4 paper, it
        # is possible, but the margins get very small to the point where the
        # crop marks may fall into the non-printable region. So make the cards
        # slightly smaller so they are safe to print.
        side_mm = 62

        tw_mm = side_mm * self.width
        th_mm = side_mm * self.height
        hmargin_mm = (w_mm - tw_mm) / 2
        vmargin_mm = (h_mm - th_mm) / 2
        # Align the table top-left with a fixed margin and leave more space at
        # the bottom, so we can put a page number there.
        vmargin_mm = hmargin_mm

        parts: List[str] = []
        parts.append(
            '<svg version="1.1" width="210mm" height="297mm" '
            'viewBox="0 0 210 297" '
            'xmlns="http://www.w3.org/2000/svg">'
        )
        parts.append(
            f"""
            <style>
            text {{ font-family: {config.font!r}; }}
            .year {{ font-size: 18px; font-weight: 900; }}
            .title, .artist, .footer {{ font-size: 5.2px; font-weight: 400; }}
            .title {{ font-style: italic; }}
            rect, line {{ stroke: black; stroke-width: 0.2; }}
            </style>
            """
        )
        if config.grid:
            parts.append(
                f'<rect x="{hmargin_mm}" y="{vmargin_mm}" '
                f'width="{tw_mm}" height="{th_mm}" '
                'fill="transparent" stroke-linejoin="miter"/>'
            )
        for ix in range(0, self.width + 1):
            x_mm = hmargin_mm + ix * side_mm
            if config.grid and ix > 0 and ix <= self.width:
                parts.append(
                    f'<line x1="{x_mm}" y1="{vmargin_mm}" '
                    f'x2="{x_mm}" y2="{vmargin_mm + th_mm}" />'
                )
            if config.crop_marks:
                parts.append(
                    f'<line x1="{x_mm}" y1="{vmargin_mm - 5}" x2="{x_mm}" y2="{vmargin_mm - 1}" />'
                    f'<line x1="{x_mm}" y1="{vmargin_mm + th_mm + 1}" x2="{x_mm}" y2="{vmargin_mm + th_mm + 5}" />'
                )

        for iy in range(0, self.height + 1):
            y_mm = vmargin_mm + iy * side_mm
            if config.grid and iy > 0 and iy <= self.height:
                parts.append(
                    f'<line x1="{hmargin_mm}" y1="{y_mm}" '
                    f'x2="{hmargin_mm + tw_mm}" y2="{y_mm}" />'
                )
            if config.crop_marks:
                parts.append(
                    f'<line x1="{hmargin_mm - 5}" y1="{y_mm}" x2="{hmargin_mm - 1}" y2="{y_mm}" />'
                    f'<line x1="{hmargin_mm + tw_mm + 1}" y1="{y_mm}" x2="{hmargin_mm + tw_mm + 5}" y2="{y_mm}" />'
                )

        for i, track in enumerate(self.cells):
            if mode == "qr":
                # Note, we mirror over the x-axis, to match the titles codes
                # when printed double-sided.
                ix = self.width - 1 - (i % self.width)
                iy = i // self.width
                qr_path, qr_mm = track.qr_svg()
                # I'm lazy so we center the QR codes, we don't resize them. If the
                # urls get longer, then the QR codes will cover a larger area of the
                # cards.
                x_mm = hmargin_mm + ix * side_mm + (side_mm - qr_mm) / 2
                y_mm = vmargin_mm + iy * side_mm + (side_mm - qr_mm) / 2
                parts.append(f'<g transform="translate({x_mm}, {y_mm})">')
                parts.append(qr_path)
                parts.append(f"</g>")

            if mode == "title":
                ix = i % self.width
                iy = i // self.width
                x_mm = hmargin_mm + (ix + 0.5) * side_mm
                y_mm = vmargin_mm + (iy + 0.5) * side_mm
                parts.append(
                    f'<text x="{x_mm}" y="{y_mm + 6.5}" text-anchor="middle" '
                    f'class="year">{track.year}</text>'
                )
                for part in render_text_svg(x_mm, y_mm - 19, track.artist, "artist"):
                    parts.append(part)
                for part in render_text_svg(x_mm, y_mm + 18, track.title, "title"):
                    parts.append(part)

        parts.append(
            f'<text x="{w_mm - hmargin_mm}" y="{h_mm - hmargin_mm}" text-anchor="end" '
            f'class="footer">{html.escape(page_footer)}</text>'
        )

        parts.append("</svg>")

        return "\n".join(parts)


def main() -> None:
    config = Config.load("mkhitsgame.toml")
    os.makedirs("out", exist_ok=True)
    os.makedirs("build", exist_ok=True)
    os.makedirs("tracks", exist_ok=True)
    os.makedirs(config.songs_dir, exist_ok=True)

    table = Table.new()
    tables: List[Table] = []
    tracks: List[Track] = []

    year_counts: Counter[int] = Counter()
    decade_counts: Counter[int] = Counter()

    # Read tracks from tracks folder
    tracks_dir = "tracks"
    
    if not os.path.exists(tracks_dir):
        print(f"Error: {tracks_dir} directory not found")
        sys.exit(1)
    
    # Supported audio file extensions
    audio_extensions = {'.mp3', '.flac', '.m4a', '.ogg', '.wav'}
    
    print(f"Processing songs from {tracks_dir}...")
    
    for filename in os.listdir(tracks_dir):
        file_path = os.path.join(tracks_dir, filename)
        
        # Skip directories and non-audio files
        if not os.path.isfile(file_path):
            continue
            
        _, ext = os.path.splitext(filename)
        if ext.lower() not in audio_extensions:
            continue
        
        # Load track from file
        track = Track.load_from_file(config, file_path)
        if track:
            tracks.append(track)
    
    # Encode tracks to output format
    print(f"\nEncoding {len(tracks)} tracks to MP4...")
    for track in tracks:
        track.encode_to_out(config)

    tracks.sort()
    for track in tracks:
        table.append(track)
        year_counts[track.year] += 1
        decade_counts[10 * (track.year // 10)] += 1

        if table.is_full():
            tables.append(table)
            table = Table.new()

    # Append the final table, which may not be full.
    if not table.is_empty():
        tables.append(table)

    # Print statistics about how many tracks we have per year and per decade, so
    # you can tweak the track selection to make the distribution somewhat more
    # even.
    print("YEAR STATISTICS")
    for year, count in sorted(year_counts.items()):
        print(f"{year}: {count:2} {'#' * count}")

    print("\nDECADE STATISTICS")
    for decade, count in sorted(decade_counts.items()):
        print(f"{decade}s: {count:2} {'#' * count}")

    print("\nTOTAL")
    print(f"{sum(decade_counts.values())} tracks")


    # For every table, write the two pages as svg.
    pdf_inputs: List[str] = []
    for i, table in enumerate(tables):
        p = i + 1
        pdf_inputs.append(f"build/{p}a.svg")
        pdf_inputs.append(f"build/{p}b.svg")
        with open(pdf_inputs[-2], "w", encoding="utf-8") as f:
            f.write(table.render_svg(config, "title", f"{p}a"))
        with open(pdf_inputs[-1], "w", encoding="utf-8") as f:
            f.write(table.render_svg(config, "qr", f"{p}b"))

    # Combine the svgs into a single pdf for easy printing.
    cmd = ["rsvg-convert", "--format=pdf", "--output=build/cards.pdf", *pdf_inputs]
    subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
