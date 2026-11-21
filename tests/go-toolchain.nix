{
  inputs,
  flakeModules,
  pkgs,
  system,
}:
let
  mkSource =
    go:
    pkgs.runCommand "go-toolchain-source" { } ''
      mkdir "$out"
      echo '{ }' > "$out/flake.nix"
      cat > "$out/go.mod" <<'EOF'
      module example.com/formatter

      go ${go.version}
      EOF
      cat > "$out/main.go" <<'EOF'
      package main

      import "fmt"

      func main() {
        fmt.Println("hello")
      }
      EOF
      ${go}/bin/gofmt -w "$out/main.go"
    '';
  mkProject =
    go: extra:
    inputs.flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ system ];
      imports = [
        flakeModules.formatting.common
        flakeModules.formatting.go
      ];
      perSystem =
        { config, ... }:
        {
          treefmt.projectRoot = mkSource go;
          packages = {
            gofmt = config.treefmt.programs.gofmt.package;
            goimports = config.treefmt.programs.goimports.package;
          };
        }
        // extra;
    };
  default = mkProject pkgs.go_latest { };
  # Trace the real Go executable: successful formatting alone cannot prove which
  # runtime goimports found, since it can suppress errors from `go list`.
  customGo = pkgs.symlinkJoin {
    name = "formatter-custom-go";
    inherit (pkgs.go) version;
    paths = [ pkgs.go ];
    nativeBuildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram "$out/bin/go" --run 'if [ -n "''${GO_SELECTION_TRACE:-}" ]; then echo selected >> "$GO_SELECTION_TRACE"; fi'
    '';
  };
  explicit = mkProject customGo { nix-tooling.go.package = customGo; };
  expectedGoimports = go: pkgs.gotools.override { inherit go; };
  customRuntime = pkgs.runCommand "go-toolchain-custom-runtime" { } ''
    export HOME="$TMPDIR"
    export GOTOOLCHAIN=local
    export GO_SELECTION_TRACE="$TMPDIR/go-selection"
    cp -r ${mkSource customGo} project
    chmod -R u+w project
    cd project
    ${explicit.packages.${system}.goimports}/bin/goimports -w main.go
    grep -Fx selected "$GO_SELECTION_TRACE"
    touch "$out"
  '';
in
assert default.packages.${system}.gofmt.drvPath == pkgs.go_latest.drvPath;
assert default.packages.${system}.goimports.drvPath == (expectedGoimports pkgs.go_latest).drvPath;
assert explicit.packages.${system}.gofmt.drvPath == customGo.drvPath;
assert explicit.packages.${system}.goimports.drvPath == (expectedGoimports customGo).drvPath;
pkgs.runCommand "go-toolchain-check"
  {
    checks = [
      default.checks.${system}.treefmt
      explicit.checks.${system}.treefmt
      customRuntime
    ];
  }
  ''
    for check in $checks; do
      test -e "$check"
    done
    touch "$out"
  ''
