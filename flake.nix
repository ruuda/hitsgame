{
  description = "Hitsgame";

  inputs = {
    nixpkgs.url = "nixpkgs/nixos-23.05";
    utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, utils }: 
  utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python311.withPackages (ps: [ps.qrcode]);
    in
      {
        devShells = {
          default = pkgs.mkShell {
            name = "hitsgame";

            nativeBuildInputs = [
              pkgs.ffmpeg
              pkgs.librsvg
              python
            ];

            LOCALE_ARCHIVE = "${pkgs.glibcLocales}/lib/locale/locale-archive";
          };
        };
      }
  );
}
