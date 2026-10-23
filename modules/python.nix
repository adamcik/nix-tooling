{
  perSystem =
    {
      config,
      lib,
      pkgs,
      ...
    }:
    {
      options.nix-tooling.ruff.source = lib.mkOption {
        type = lib.types.path;
        default = config.treefmt.projectRoot;
        defaultText = lib.literalExpression "config.treefmt.projectRoot";
        description = ''
          Source tree inspected by the Ruff lint check. Set this to a filtered
          source to avoid rebuilding the check for unrelated changes. Preserve
          relative paths and include all Ruff configuration files, including
          inherited configuration. This does not restrict treefmt formatting.
        '';
      };

      config = {
        treefmt.programs.ruff-format.enable = true;

        # Keep linting separate and override any fix=true in project configuration.
        checks.ruff =
          pkgs.runCommand "ruff-check"
            {
              nativeBuildInputs = [ config.treefmt.programs.ruff-format.package ];
            }
            ''
              cd ${lib.escapeShellArg "${config.nix-tooling.ruff.source}"}
              ruff check --no-fix --no-cache .
              touch "$out"
            '';
      };
    };
}
