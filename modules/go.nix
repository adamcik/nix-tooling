{
  perSystem =
    {
      config,
      lib,
      pkgs,
      ...
    }:
    {
      options.nix-tooling.go.package = lib.mkOption {
        type = lib.types.package;
        default = pkgs.go_latest;
        defaultText = lib.literalExpression "pkgs.go_latest";
        description = ''
          Go toolchain used by gofmt and the goimports runtime. Defaults to the
          latest Go in the consumer's pinned nixpkgs, so formatting does not
          need to download a toolchain for modules requiring that version.
        '';
      };

      config.treefmt = {
        programs.gofmt = {
          enable = true;
          package = lib.mkDefault config.nix-tooling.go.package;
        };
        programs.goimports = {
          enable = true;
          package = lib.mkDefault (pkgs.gotools.override { go = config.nix-tooling.go.package; });
        };
        settings.formatter.gofmt.priority = 1;
        settings.formatter.goimports.priority = 2;
      };
    };
}
