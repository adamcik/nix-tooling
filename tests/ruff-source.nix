{
  inputs,
  flakeModules,
  pkgs,
  system,
}:
let
  mkProject =
    extra:
    inputs.flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ system ];
      imports = [
        flakeModules.formatting.common
        flakeModules.formatting.python
      ];
      perSystem = {
        treefmt.projectRoot = ./fixtures;
      }
      // extra;
    };
  default = mkProject { };
  explicit = mkProject { nix-tooling.ruff.source = ./fixtures; };
  mkSource =
    select:
    pkgs.runCommand "ruff-source" { } ''
      mkdir -p "$out/src" "$out/tests"
      echo 'import os' > "$out/src/example.py"
      echo 'assert True' > "$out/tests/test_example.py"
      cat > "$out/pyproject.toml" <<'EOF'
      [tool.ruff]
      extend = "rules.toml"
      EOF
      cat > "$out/rules.toml" <<'EOF'
      [lint]
      select = ["${select}"]
      EOF
    '';
  configured = select: mkProject { nix-tooling.ruff.source = mkSource select; };
  passing = configured "E";
  failing = (configured "F").checks.${system}.ruff;
  expectedFailure = failing.overrideAttrs (old: {
    name = "ruff-source-expected-failure";
    buildCommand = ''
      if bash -e ${pkgs.writeText "ruff-command" old.buildCommand} > ruff.log 2>&1; then
        echo "Ruff accepted an unused import despite the inherited F rules" >&2
        exit 1
      fi
      grep -F 'F401' ruff.log
      grep -F 'src/example.py' ruff.log
      touch "$out"
    '';
  });
in
assert default.checks.${system}.ruff.drvPath == explicit.checks.${system}.ruff.drvPath;
assert default.checks.${system}.treefmt.drvPath == passing.checks.${system}.treefmt.drvPath;
assert default.formatter.${system}.drvPath == passing.formatter.${system}.drvPath;
pkgs.runCommand "ruff-source-check"
  {
    checks = [
      default.checks.${system}.ruff
      passing.checks.${system}.ruff
      expectedFailure
    ];
  }
  ''
    for check in $checks; do
      test -e "$check"
    done
    touch "$out"
  ''
