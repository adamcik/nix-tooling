{ pkgs, actionlint }:
pkgs.runCommand "actionlint-runner-labels-check" { nativeBuildInputs = [ actionlint ]; } ''
  workflow() {
    cat <<EOF
  on: push
  jobs:
    check:
      runs-on: $1
      steps:
        - run: $2
  EOF
  }

  for labels in ubuntu-24.04 ubuntu-26.04 ubuntu-26.04-arm '[self-hosted, linux, ubuntu-26.04]'; do
    workflow "$labels" 'echo ok' | actionlint -
  done

  cat <<'EOF' | actionlint -
  on: push
  jobs:
    check:
      strategy:
        matrix:
          os: [ubuntu-26.04, ubuntu-26.04-arm]
      runs-on: ''${{ matrix.os }}
      steps:
        - run: echo ok
  EOF

  reject() {
    labels="$1"
    command="$2"
    diagnostic="$3"
    if workflow "$labels" "$command" | actionlint - > rejected.log 2>&1; then
      echo "Accepted invalid workflow: $labels / $command" >&2
      exit 1
    fi
    grep -F "$diagnostic" rejected.log
  }

  reject ubuntu-99.04 'echo ok' '[runner-label]'
  reject '[ubuntu-26.04, windows-2025]' 'echo ok' 'conflicts with label'
  reject '[ubuntu-26.04, ubuntu-24.04]' 'echo ok' 'conflicts with label'
  reject ubuntu-26.04 'echo $value' '[shellcheck]'
  touch "$out"
''
