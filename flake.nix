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

  outputs =
    inputs@{
      self,
      nixpkgs,
      flake-parts,
      treefmt-nix,
      kakehashi,
    }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      imports = [
        treefmt-nix.flakeModule
      ];

      perSystem =
        {
          config,
          self',
          inputs',
          pkgs,
          system,
          ...
        }:
        {
          # treefmt configuration
          treefmt = {
            projectRootFile = "flake.nix";
            programs = {
              nixfmt.enable = true;
              ruff-format.enable = true;
              yamlfmt.enable = true;
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
          # Note: treefmt-nix flake module auto-creates checks.treefmt and
          # formatter output when flakeCheck/flakeFormatter are true (default).
          # Do NOT manually set formatting = config.treefmt.build.check here
          # because build.check is now a function (takes projectRoot), not a derivation.
          checks = {
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

            # Markdownlint check
            markdownlint = pkgs.stdenv.mkDerivation {
              name = "markdownlint-check";
              src = self;
              nativeBuildInputs = [ pkgs.markdownlint-cli ];
              buildPhase = ''
                markdownlint "**/*.md" || {
                  echo "markdownlint found issues"
                  exit 1
                }
              '';
              installPhase = "mkdir -p $out";
            };

            # Textlint check
            textlint = pkgs.stdenv.mkDerivation {
              name = "textlint-check";
              src = self;
              nativeBuildInputs = [ pkgs.textlint ];
              buildPhase = ''
                textlint "**/*.md" || {
                  echo "textlint found issues"
                  exit 1
                }
              '';
              installPhase = "mkdir -p $out";
            };

            # Yamllint check (YAML syntax)
            yamllint = pkgs.stdenv.mkDerivation {
              name = "yamllint-check";
              src = self;
              nativeBuildInputs = [ pkgs.yamllint ];
              buildPhase = ''
                yamllint . || {
                  echo "yamllint found issues"
                  exit 1
                }
              '';
              installPhase = "mkdir -p $out";
            };

            # Actionlint check (GitHub Actions)
            actionlint = pkgs.stdenv.mkDerivation {
              name = "actionlint-check";
              src = self;
              nativeBuildInputs = [ pkgs.actionlint ];
              buildPhase = ''
                actionlint .github/workflows/*.yml || {
                  echo "actionlint found issues"
                  exit 1
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
