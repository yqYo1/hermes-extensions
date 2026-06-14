{
  description = "Hermes Agent extensions - plugins and skills collection";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    treefmt-nix.url = "github:numtide/treefmt-nix";
    kakehashi = {
      url = "github:atusy/kakehashi";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs@{ self, nixpkgs, flake-parts, treefmt-nix, kakehashi }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      imports = [
        treefmt-nix.flakeModule
      ];

      perSystem = { config, self', inputs', pkgs, system, ... }: {
        # treefmt configuration
        treefmt = {
          projectRootFile = "flake.nix";
          programs = {
            nixfmt.enable = true;
            ruff = {
              enable = true;
              format = true;
            };
            yamlfmt.enable = true;
          };
          settings = {
            formatter = {
              nixfmt = {
                includes = [ "*.nix" ];
              };
              ruff = {
                includes = [ "*.py" ];
              };
              yamlfmt = {
                includes = [ "*.yaml" "*.yml" ];
              };
              kakehashi = {
                command = "${kakehashi.packages.${system}.default}/bin/kakehashi";
                options = [ "format" ];
                includes = [ "*.md" ];
              };
            };
          };
        };

        # Packages for checks
        packages = {
          basedpyright = pkgs.basedpyright;
          ty = pkgs.python312Packages.ty;
          typos = pkgs.typos;
          kakehashi = kakehashi.packages.${system}.default;
        };

        # Checks
        checks = {
          # Format check (treefmt --fail-on-change)
          formatting = config.treefmt.build.check;

          # Typos check
          typos = pkgs.stdenv.mkDerivation {
            name = "typos-check";
            src = self;
            nativeBuildInputs = [ pkgs.typos ];
            buildPhase = "typos";
            installPhase = "mkdir -p $out";
          };

          # Basedpyright check (strict - must pass)
          basedpyright = pkgs.stdenv.mkDerivation {
            name = "basedpyright-check";
            src = self;
            nativeBuildInputs = [ pkgs.basedpyright ];
            buildPhase = ''
              basedpyright \
                --outputjson \
                --project . \
                || { echo "basedpyright found issues"; exit 1; }
            '';
            installPhase = "mkdir -p $out";
          };

          # Ty check (experimental - allowed to fail)
          ty = pkgs.stdenv.mkDerivation {
            name = "ty-check";
            src = self;
            nativeBuildInputs = [ pkgs.python312Packages.ty ];
            buildPhase = ''
              echo "Running ty (experimental type checker)..."
              ty check . || {
                echo "ty found issues (experimental - not failing CI)"
                exit 0
              }
            '';
            installPhase = "mkdir -p $out";
          };

          # Kakehashi check (markdown code block formatting)
          kakehashi = pkgs.stdenv.mkDerivation {
            name = "kakehashi-check";
            src = self;
            nativeBuildInputs = [ kakehashi.packages.${system}.default ];
            buildPhase = ''
              kakehashi format --check --fail-on-change .
            '';
            installPhase = "mkdir -p $out";
          };
        };

        # Development shell
        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.basedpyright
            pkgs.python312Packages.ty
            pkgs.typos
            kakehashi.packages.${system}.default
            config.treefmt.build.wrapper
          ];
        };
      };
    };
}
