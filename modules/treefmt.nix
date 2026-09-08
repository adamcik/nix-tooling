{
  perSystem = { pkgs, ... }: {
    treefmt = {
      projectRootFile = "flake.nix";
      flakeFormatter = true;
      flakeCheck = true;
      programs.nixfmt.enable = true;
      programs.actionlint.enable = true;
      programs.dprint = {
        enable = true;
        includes = [
          "*.md"
          "*.markdown"
          "*.json"
          "*.jsonc"
          "*.toml"
        ];
        settings = {
          plugins = pkgs.dprint-plugins.getPluginList (plugins: [
            plugins.dprint-plugin-markdown
            plugins.dprint-plugin-json
            plugins.dprint-plugin-toml
          ]);
          markdown = {
            lineWidth = 88;
            textWrap = "always";
          };
        };
      };
    };
  };
}
