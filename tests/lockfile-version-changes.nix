{ pkgs }:
pkgs.runCommand "lockfile-version-changes-check"
  {
    nativeBuildInputs = [
      pkgs.action-validator
      pkgs.python3
      pkgs.ruff
    ];
  }
  ''
    cp ${../actions/lockfile-version-changes/action.yml} action.yml
    action-validator action.yml
    ruff check --no-cache --target-version py311 --select E,F,I,S --ignore E501,S101 \
      ${../actions/lockfile-version-changes/lockfile_version_changes.py} \
      ${./test_lockfile_version_changes.py}
    LOCKFILE_VERSION_CHANGES_SCRIPT=${../actions/lockfile-version-changes/lockfile_version_changes.py} \
      python3 ${./test_lockfile_version_changes.py}
    touch "$out"
  ''
