{ pkgs }:
# Validate the action locally without installing Nix or running destructive cleanup.
pkgs.runCommand "nix-setup-check"
  {
    nativeBuildInputs = [
      pkgs.action-validator
      pkgs.yq-go
      pkgs.shellcheck
    ];
  }
  ''
    # The validator selects the action schema by the exact filename.
    cp ${../actions/nix-setup/action.yml} action.yml
    action-validator action.yml
    action-validator ${../.github/workflows/ci.yml}
    yq -r '.runs.steps[0].run' action.yml > validate.sh
    shellcheck --shell=bash validate.sh

    export RUNNER_ENVIRONMENT=github-hosted RUNNER_OS=Linux RUNNER_ARCH=X64
    MAKE_SPACE=false bash -euo pipefail validate.sh
    MAKE_SPACE=true bash -euo pipefail validate.sh

    for value in "" yes TRUE; do
      if MAKE_SPACE="$value" bash -euo pipefail validate.sh > rejected.log 2>&1; then
        echo "Accepted invalid make-space value: $value" >&2
        exit 1
      fi
    done
    export MAKE_SPACE=true
    for setting in RUNNER_ENVIRONMENT=self-hosted RUNNER_OS=macOS RUNNER_OS=Windows RUNNER_ARCH=ARM64; do
      if env "$setting" bash -euo pipefail validate.sh > rejected.log 2>&1; then
        echo "Accepted unsupported runner: $setting" >&2
        exit 1
      fi
    done
    touch "$out"
  ''
