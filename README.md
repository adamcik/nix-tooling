# nix-tooling

nix-tooling provides shared formatting and lint checks for repositories that use Nix
flakes and `flake-parts`. Import `common` and the language modules you need, then run
`nix fmt` to format your files and `nix flake check` to check them.

You choose the modules explicitly. They do not detect languages, build applications,
manage dependencies, or add development shells. A separate
[GitHub Actions setup action](#github-actions) installs Nix without choosing what your
CI runs.

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

## GitHub Actions

Use `actions/nix-setup` to install upstream Nix on a GitHub-hosted x86_64 Ubuntu runner.
The action is independent of the flake modules; your repository does not need to use
flake-parts to call it.

```yaml
permissions:
  contents: read

jobs:
  check:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: adamcik/nix-tooling/actions/nix-setup@COMMIT_SHA
      # Add repository-specific cache setup here, if needed.
      - run: nix flake check
```

Replace `COMMIT_SHA` with the full commit SHA of the nix-tooling version you want to
use. This pin is separate from your flake input. Add your own workflow triggers.

The action uses Cachix's Nix installer, but does not configure Cachix, Attic, or any
other additional cache. It does not check out code, update locks, format files, or run
builds. You choose the commands: for example, `nix flake check --no-build` for
evaluation only, `nix flake check` to build declared checks, or a selected `nix build`
target. The installer enables flakes and uses the job's GitHub token for Nix fetches by
default.

### Private Flake Inputs

To fetch inputs from other private GitHub repositories, pass a token with read access to
those repositories. The job's default token is scoped to the caller repository.

```yaml
- uses: adamcik/nix-tooling/actions/nix-setup@COMMIT_SHA
  with:
    github-token: ${{ secrets.NIX_GITHUB_TOKEN }}
```

You can also pass a token generated by a preceding GitHub App step. The installer writes
`access-tokens = github.com=<token>` to `/etc/nix/nix.conf`; it does not set the
`NIX_CONFIG` environment variable. Later Nix commands use that configuration. Do not
print the configuration or pass a privileged token to jobs running untrusted
pull-request code.

### Optional Disk Cleanup

Set `make-space: "true"` to run
[Nothing but Nix](https://github.com/wimpysworld/nothing-but-nix) before installing Nix:

```yaml
- uses: adamcik/nix-tooling/actions/nix-setup@COMMIT_SHA
  with:
    make-space: "true"
```

The default is `"false"`. When enabled, cleanup uses upstream's `cleave` mode and waits
for completion. It removes preinstalled software, including Docker, tool caches,
language SDKs, and `/usr/local`, then combines disk space into a Btrfs volume for
`/nix`. It reserves 2 GiB on `/` and 1 GiB on `/mnt` using upstream defaults. Run it
before installing other job tools, and do not enable it if later steps need the removed
software. Cleanup requires Nix not to be installed already.

Only the exact strings `"true"` and `"false"` are accepted. Self-hosted, ARM, macOS, and
Windows runners are rejected before cleanup or installation.

## Development

Before submitting changes, run `nix fmt` and `nix flake check`. This repository uses its
own `common` module. Its checks also combine all exported modules and run them against
small sample files. The `nix-setup` check validates the action and workflow schemas and
tests the setup guards without installing Nix or deleting runner software.

The GitHub CI workflow uses the local setup action before running flake checks. Its
manual trigger can enable `make-space` to exercise cleanup on a disposable runner;
normal push and pull-request runs leave cleanup disabled.

This repository tests `x86_64-linux` only. Your repository chooses its own systems; the
exported modules do not set them.

## License

Licensed under the [Apache License 2.0](LICENSE).
