{
  perSystem.treefmt = {
    programs.gofmt.enable = true;
    programs.goimports.enable = true;
    settings.formatter.gofmt.priority = 1;
    settings.formatter.goimports.priority = 2;
  };
}
