{
  description = "Small, composable flake-parts tooling modules";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    flake-parts.inputs.nixpkgs-lib.follows = "nixpkgs";
    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    inputs@{ flake-parts, treefmt-nix, ... }:
    let
      flakeModules.formatting = {
        common = {
          imports = [
            treefmt-nix.flakeModule
            ./modules/treefmt.nix
          ];
        };
        python = ./modules/python.nix;
        django = ./modules/django.nix;
        go = ./modules/go.nix;
        rust = ./modules/rust.nix;
        web = ./modules/web.nix;
        terraform = ./modules/terraform.nix;
      };
    in
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" ];
      imports = [ flakeModules.formatting.common ];
      flake = { inherit flakeModules; };

      perSystem =
        { system, ... }:
        let
          composed = flake-parts.lib.mkFlake { inherit inputs; } {
            systems = [ system ];
            imports = builtins.attrValues flakeModules.formatting;
            perSystem.treefmt.projectRoot = ./tests/fixtures;
          };
        in
        {
          checks.modules-format = composed.checks.${system}.treefmt;
          checks.modules-ruff = composed.checks.${system}.ruff;
        };
    };
}
