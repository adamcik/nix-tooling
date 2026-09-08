{
  perSystem = { config, pkgs, ... }: {
    treefmt.programs.ruff-format.enable = true;

    # Keep linting separate and override any fix=true in project configuration.
    checks.ruff =
      pkgs.runCommand "ruff-check"
        {
          nativeBuildInputs = [ config.treefmt.programs.ruff-format.package ];
        }
        ''
          cd ${config.treefmt.projectRoot}
          ruff check --no-fix --no-cache .
          touch "$out"
        '';
  };
}
