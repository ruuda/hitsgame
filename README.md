# Hitsgame

Build your own version of the game [Hitster][hitster]. The resulting cards
contain a QR code that point to an audio file on a webserver, no Spotify is
needed to play.

## Ingredients

Ingredients:

 * A collection of properly tagged flac files. These files must have the
   `TITLE`, `ARTIST`, and `ORIGINALDATE` or `DATE` tags set.
 * A webserver that can serve static files.
 * Sheets of A4 paper, preferably 180 g/m².
 * Tokens from the original Hitster game, or a suitable replacement,
   e.g. poker chips.

Hardware tools needed:

 * A printer.
 * Preferably a paper cutter, alternatively scissors.

Software tools needed:

 * Either [Nix 2.17.0][nix217], which can provide all other needed packages,
   run with `nix develop --command mkhitsgame.py`.
 * Or installed manually:
   * Python with `qrcode==7.4.2` package.
   * ffmpeg n6.1.
   * rsvg-convert (from librsvg) 2.57.1.

## Preparation

 1. Create a directory named `tracks` and put the tracks in there that you want
    to include.
 2. Create a file named `mkhitsgame.toml` next to the `tracks` directory, and
    add the configuration as shown in the next section.
 3. Run `mkhitsgame.py`. It will print statistics about the track distribution
    over years and and decades, so you can tweak the track selection to balance
    out the game.
 4. You now have two new directories: `build` and `out`. `out` contains the
    tracks, compressed and anonymized. These files contain no metadata, and the
    file names are long enough to be virtually unguessable, so they are safe to
    serve from a public webserver without additional authentication. `build`
    contains the pdf with the cards, as well as intermediate svg files.
 5. Upload the contents of `out` to your webserver.
 6. Print `build/cards.pdf` and cut out the cards.

## Configuration

The `mkhitsgame.toml` file follows the following format:

```toml
# The url prefix that your webserver will serve the track mp4s from.
url_prefix = "https://example.com/"

# Font to use on the cards.
font = "Cantarell"

# Whethes to draw a grid around the cards. If you want to inspect the pdf on
# your computer, or if you are cutting the cards with scissors, you probably
# want to enable this. If you are cutting with a paper cutter, you should
# disable the grid, because if you don't cut *exactly* on the line you'll end
# up with ugly lines on the sides of the cards.
grid = true

# Whether to include crop marks at the sides of the page. If you are cutting
# with a paper cutter, you should enable this to know where to cut.
crop_marks = false
```

For the webserver, you need to configure it to serve the `.mp4` files with
`audo/mp4` MIME type. For Nginx, you can do this using the following snippet:

```nginx
types {
  audio/mp4 mp4;
}
```

## How to play

Refer [the original game rules][howplay] for how to play the game itself. You
do not need to connect Spotify. Scanning a QR code will open the track in your
browser. Most browsers will auto-play the track.

## License

Hitsgame is free software. It is licensed under the
[GNU General Public License][gplv3], version 3.

[gplv3]:   https://www.gnu.org/licenses/gpl-3.0.html
[hitster]: https://boardgamegeek.com/boardgame/318243/hitster
[howplay]: https://hitstergame.com/en-us/how-to-play-premium/
[nix217]:  https://nixos.org/download#nix-more
