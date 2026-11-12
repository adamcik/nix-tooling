{ pkgs, formatter }:
pkgs.runCommand "markdown-format-check" { nativeBuildInputs = [ formatter ]; } ''
  touch flake.nix
  cp ${./fixtures/example.md} expected.md
  for extension in md markdown; do
    # Both extensions must reflow prose and align tables wider than the prose limit.
    cat > "example.$extension" <<'EOF'
  # Markdown

  Readable prose wraps around eighty-eight
  columns without squeezing wide Markdown tables.

  | Module | Responsibility |
  | --- | --- |
  | treefmt | Common repository formatting, including readable Markdown prose and aligned tables that may exceed eighty-eight columns. |
  EOF
    treefmt --no-cache "example.$extension"
    diff -u expected.md "example.$extension"
    treefmt --no-cache --fail-on-change "example.$extension"
  done
  test ! -e .rumdl_cache
  touch "$out"
''
