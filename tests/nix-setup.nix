{ pkgs }:
# Validate the action locally without installing Nix or running destructive cleanup.
pkgs.runCommand "nix-setup-check"
  {
    nativeBuildInputs = [
      pkgs.action-validator
      pkgs.yq-go
      pkgs.jq
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
    for make_space in false true; do
      for trust_runner in false true; do
        MAKE_SPACE="$make_space" TRUST_RUNNER_USER="$trust_runner" \
          bash -euo pipefail validate.sh
      done
    done

    export MAKE_SPACE=false TRUST_RUNNER_USER=true
    for input in MAKE_SPACE TRUST_RUNNER_USER; do
      for value in "" yes TRUE; do
        if env "$input=$value" bash -euo pipefail validate.sh > rejected.log 2>&1; then
          echo "Accepted invalid $input value: $value" >&2
          exit 1
        fi
      done
    done
    export MAKE_SPACE=true
    for setting in RUNNER_ENVIRONMENT=self-hosted RUNNER_OS=macOS RUNNER_OS=Windows RUNNER_ARCH=ARM64; do
      if env "$setting" bash -euo pipefail validate.sh > rejected.log 2>&1; then
        echo "Accepted unsupported runner: $setting" >&2
        exit 1
      fi
    done

    # Check wiring without installing Nix or removing any files.
    yq -o=json action.yml > action.json
    export FULL_CLEANUP_CONDITION="inputs.make-space == 'true'"
    jq -e '.runs.steps[] | select(.name == "Make space for Nix") |
      .if == env.FULL_CLEANUP_CONDITION' action.json >/dev/null
    jq -e '.runs.steps[] | select(.name == "Install Nix") |
      (.with.set_as_trusted_user == "\u0024{{ inputs.trust-runner-user }}") and
      (.with.extra_nix_config == "\u0024{{ inputs.extra-conf }}") and
      (.with.github_access_token == "\u0024{{ inputs.github-token }}")' action.json >/dev/null
    touch "$out"
  ''
