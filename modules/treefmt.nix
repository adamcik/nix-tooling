{
  perSystem =
    {
      config,
      lib,
      pkgs,
      ...
    }:
    {
      checks.rumdl =
        pkgs.runCommand "rumdl-check"
          {
            nativeBuildInputs = [ config.treefmt.programs.rumdl-format.package ];
          }
          ''
            cd ${lib.escapeShellArg "${config.treefmt.projectRoot}"}
            rumdl check ${
              lib.escapeShellArgs (
                lib.filter (arg: arg != "fmt") config.treefmt.settings.formatter.rumdl-format.options
              )
            } --fail-on any .
            touch "$out"
          '';

      treefmt = {
        projectRootFile = "flake.nix";
        flakeFormatter = true;
        flakeCheck = true;
        programs.nixfmt.enable = true;
        programs.actionlint = {
          enable = true;
          package = pkgs.callPackage ../packages/actionlint.nix { };
        };
        programs.rumdl-format = {
          enable = true;
          includes = [
            "*.md"
            "*.markdown"
          ];
        };
        settings.formatter.rumdl-format.options = [
          # treefmt handles caching; avoid creating rumdl caches in consumer checkouts.
          "--no-cache"
          "--config"
          "MD013.line-length = 88"
          "--config"
          "MD013.reflow = true"
          "--config"
          "MD013.reflow-mode = 'normalize'"
          "--config"
          "MD013.code-blocks = false"
          "--config"
          "MD013.tables = false"
          "--config"
          "MD060.enabled = true"
          "--config"
          "MD060.style = 'aligned'"
        ];
        programs.dprint = {
          enable = true;
          includes = [
            "*.json"
            "*.jsonc"
            "*.toml"
          ];
          settings = {
            plugins = pkgs.dprint-plugins.getPluginList (plugins: [
              plugins.dprint-plugin-json
              plugins.dprint-plugin-toml
            ]);
          };
        };
      };
    };
}
