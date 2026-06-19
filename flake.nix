{
  description = "Hermes Agent extensions - plugins and skills collection";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    kakehashi = {
      url = "github:atusy/kakehashi";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    hermes-agent = {
      url = "github:NousResearch/hermes-agent";
      flake = false;
    };
  };

  outputs =
    inputs@{
      self,
      nixpkgs,
      flake-parts,
      treefmt-nix,
      kakehashi,
      hermes-agent,
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

            # Basedpyright check against latest hermes-agent (strict - must pass)
            basedpyright-latest = pkgs.stdenv.mkDerivation {
              name = "basedpyright-check-latest";
              src = self;
              nativeBuildInputs = [ pkgs.basedpyright ];
              buildPhase = ''
                mkdir -p .hermes
                cp -r ${hermes-agent} .hermes/hermes-agent
                cat > pyrightconfig.json << 'EOF'
                {
                  "extraPaths": [".hermes/hermes-agent"]
                }
                EOF
                basedpyright \
                  --outputjson \
                  --project . \
                  > basedpyright-output.json 2>&1 || true
                # Parse JSON output - fail only on actual errors, not warnings
                if [ -f basedpyright-output.json ]; then
                  ERRORS=$(grep -o '"errorCount":[0-9]*' basedpyright-output.json | cut -d: -f2)
                  echo "basedpyright: $ERRORS error(s) found"
                  if [ "$ERRORS" -gt 0 ]; then
                    echo "basedpyright found errors"
                    cat basedpyright-output.json
                    exit 1
                  fi
                  echo "basedpyright passed (warnings only)"
                fi
              '';
              installPhase = "mkdir -p $out";
            };

            # Basedpyright check against local hermes-agent (strict - must pass)
            basedpyright-local = pkgs.stdenv.mkDerivation {
              name = "basedpyright-check-local";
              src = self;
              nativeBuildInputs = [ pkgs.basedpyright ];
              buildPhase = ''
                if [ -d "${self}/.hermes/hermes-agent" ]; then
                  cp -r ${self}/.hermes/hermes-agent .hermes/hermes-agent
                  printf '%s\n' '{"extraPaths": [".hermes/hermes-agent"]}' > pyrightconfig.json
                  basedpyright \
                    --outputjson \
                    --project . \
                    > basedpyright-output.json 2>&1 || true
                  if [ -f basedpyright-output.json ]; then
                    ERRORS=$(grep -o '"errorCount":[0-9]*' basedpyright-output.json | cut -d: -f2)
                    echo "basedpyright: $ERRORS error(s) found"
                    if [ "$ERRORS" -gt 0 ]; then
                      echo "basedpyright found errors"
                      cat basedpyright-output.json
                      exit 1
                    fi
                    echo "basedpyright passed (warnings only)"
                  fi
                else
                  echo "Local hermes-agent not found, skipping local check"
                fi
                mkdir -p "$out"
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
