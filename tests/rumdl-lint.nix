{
  inputs,
  flakeModules,
  pkgs,
  system,
}:
let
  source = pkgs.runCommand "markdown-lint-source" { } ''
    mkdir "$out"
    cat > "$out/example.markdown" <<'EOF'
    # Example

    ## Repeated

    ## Repeated
    EOF
  '';
  project = inputs.flake-parts.lib.mkFlake { inherit inputs; } {
    systems = [ system ];
    imports = [ flakeModules.formatting.common ];
    perSystem.treefmt.projectRoot = source;
  };
  check = project.checks.${system}.rumdl;
in
check.overrideAttrs (old: {
  name = "rumdl-lint-expected-failure";
  buildCommand = ''
    if bash -e ${pkgs.writeText "rumdl-command" old.buildCommand} > rumdl.log 2>&1; then
      echo "rumdl accepted duplicate headings" >&2
      exit 1
    fi
    grep -F 'MD024' rumdl.log
    grep -F 'example.markdown' rumdl.log
    touch "$out"
  '';
})
