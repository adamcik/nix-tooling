{ pkgs }:
# Exercise command ordering and failures offline; provenance verification stays in CI.
pkgs.runCommand "verify-actions-lock-check"
  {
    nativeBuildInputs = [
      pkgs.action-validator
      pkgs.yq-go
      pkgs.jq
      pkgs.shellcheck
    ];
  }
  ''
    cp ${../actions/verify-actions-lock/action.yml} action.yml
    action-validator action.yml
    yq -o=json action.yml > action.json
    jq -e '
      .inputs["github-token"].default == "\u0024{{ github.token }}" and
      .runs.using == "composite" and
      (.runs.steps | length) == 1 and
      .runs.steps[0].shell == "bash" and
      .runs.steps[0].env.GH_TOKEN == "\u0024{{ inputs.github-token }}"
    ' action.json > /dev/null
    export ACTIONS_LOCK_VERSION="$(yq -r '.runs.steps[0].env.ACTIONS_LOCK_VERSION' action.yml)"
    [[ "$ACTIONS_LOCK_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]
    yq -r '.runs.steps[0].run' action.yml > verify.sh
    shellcheck --shell=bash verify.sh

    mkdir bin
    cat > bin/gh <<'SH'
    #!${pkgs.runtimeShell}
    set -euo pipefail
    [[ "$GH_TOKEN" == test-token ]]
    printf '%s\n' "$*" >> "$GH_TEST_LOG"
    case "$1" in
      extension)
        [[ "$*" == "extension install github/gh-actions-lock --pin $ACTIONS_LOCK_VERSION --force" ]]
        exit "$GH_TEST_INSTALL_EXIT"
        ;;
      actions-lock)
        [[ "$*" == "actions-lock --verify" ]]
        exit "$GH_TEST_VERIFY_EXIT"
        ;;
      *) exit 99 ;;
    esac
    SH
    chmod +x bin/gh
    export PATH="$PWD/bin:$PATH" GH_TOKEN=test-token
    export GH_TEST_LOG="$PWD/commands.log"
    export GH_TEST_INSTALL_EXIT=0 GH_TEST_VERIFY_EXIT=0

    bash -euo pipefail verify.sh
    printf 'extension install github/gh-actions-lock --pin %s --force\nactions-lock --verify\n' \
      "$ACTIONS_LOCK_VERSION" > expected.log
    diff -u expected.log commands.log

    : > commands.log
    export GH_TEST_INSTALL_EXIT=17
    status=0
    bash -euo pipefail verify.sh || status=$?
    test "$status" -eq 17
    test "$(wc -l < commands.log)" -eq 1

    : > commands.log
    export GH_TEST_INSTALL_EXIT=0 GH_TEST_VERIFY_EXIT=23
    status=0
    bash -euo pipefail verify.sh || status=$?
    test "$status" -eq 23
    diff -u expected.log commands.log
    touch "$out"
  ''
