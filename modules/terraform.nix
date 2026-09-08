{
  perSystem = { pkgs, ... }: {
    treefmt.programs.terraform = {
      enable = true;
      package = pkgs.opentofu;
    };
  };
}
