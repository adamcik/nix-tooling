# nix-tooling

nix-tooling provides shared formatting and lint checks for repositories that use Nix
flakes and `flake-parts`. Import `common` and the language modules you need, then run
`nix fmt` to format your files and `nix flake check` to check them.

You choose the modules explicitly. They do not detect languages, build applications,
manage dependencies, or add development shells.

## Setup

Add these inputs to your existing `flake.nix`:

```nix
inputs.nix-tooling.url = "github:adamcik/nix-tooling";
inputs.nix-tooling.inputs.nixpkgs.follows = "nixpkgs";
```

Import `common` alongside your language modules inside `flake-parts.lib.mkFlake`. You do
not need a separate treefmt-nix input: the `common` module imports it for you.

For a Python project with Django templates:

```nix
outputs = inputs@{ flake-parts, ... }:
  flake-parts.lib.mkFlake { inherit inputs; } {
    systems = [ "x86_64-linux" ];
    imports = [
      inputs.nix-tooling.flakeModules.formatting.common
      inputs.nix-tooling.flakeModules.formatting.python
      inputs.nix-tooling.flakeModules.formatting.django
    ];
  };
```

For Go, use these imports instead:

```nix
imports = [
  inputs.nix-tooling.flakeModules.formatting.common
  inputs.nix-tooling.flakeModules.formatting.go
];
```

Always include `common`; the language modules depend on it. When migrating, remove
previous flake formatter assignments and Alejandra configuration. All Nix files use
**nixfmt**.

## Choose Modules

All modules below are exported under `flakeModules.formatting`. They configure
formatting and related checks, not development shells or application builds.

| Module      | Tools and files                                             |
| ----------- | ----------------------------------------------------------- |
| `common`    | nixfmt, dprint for Markdown/JSON/JSONC/TOML, and actionlint |
| `python`    | Ruff formatting and a separate, non-fixing `checks.ruff`    |
| `django`    | djlint for `*.html`, `*.jinja`, `*.jinja2`, and `*.j2`      |
| `go`        | gofmt, followed by goimports                                |
| `rust`      | rustfmt (upstream defaults to edition 2024)                 |
| `web`       | oxfmt for JS/TS, CSS/SCSS, Vue, GraphQL, MDX, and YAML      |
| `terraform` | OpenTofu `fmt` for Terraform configuration                  |

Markdown prose wraps at about 88 columns. Tables keep aligned columns even when they
exceed that width.

The `web` module leaves standalone HTML to djlint and Markdown, JSON, JSONC, and TOML to
dprint. This prevents those formatters from processing the same files. Add other
formatters explicitly if your project needs file types not listed here.

## Format and Check

Run these commands from your repository:

```sh
nix fmt
nix flake check
```

`nix fmt` runs the treefmt wrapper to format files with the tools you selected. It also
runs actionlint to check GitHub Actions workflows.

`nix flake check` automatically includes `checks.treefmt`. That check fails if files
need formatting or actionlint reports errors. The `python` module also adds
`checks.ruff`, which checks Python lint rules without changing files. Ruff linting runs
separately from formatting, so `nix fmt` does not apply Ruff lint fixes.

Flake checks use the Nix source snapshot. For Git-based flakes, add new files to Git
before checking them. dprint plugins come from nixpkgs; checks do not download them
inside the build sandbox.

## Customize Settings

Use treefmt-nix options in `perSystem`. Lists merge with the module defaults; use
`lib.mkForce` when you want to replace a list:

```nix
perSystem = { lib, ... }: {
  treefmt.programs.djlint.excludes = [ "vendor/*" "generated/*" ];
  treefmt.programs.djlint.includes = lib.mkForce [ "templates/*.html" ];
  treefmt.programs.rustfmt.edition = "2021";
};
```

Select a template profile in your djlint project configuration.

Ruff reads your `pyproject.toml` or Ruff configuration. Its lint check does not use
treefmt exclusions. To exclude files from Ruff linting, set `extend-exclude` under
`[tool.ruff]` in `pyproject.toml`, or use the equivalent Ruff configuration.

Additional checks are opt-in. Enable treefmt-nix's `zizmor`, `shellcheck`, `shfmt`,
`deadnix`, or `statix` programs in your repository if you need them.

## Development

Before submitting changes, run `nix fmt` and `nix flake check`. This repository uses its
own `common` module. Its checks also combine all exported modules and run them against
small sample files.

This repository tests `x86_64-linux` only. Your repository chooses its own systems; the
exported modules do not set them.

## License

Licensed under the [Apache License 2.0](LICENSE).
