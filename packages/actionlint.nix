{ actionlint }:
actionlint.overrideAttrs (old: {
  # Official hosted images must retain actionlint's OS compatibility checks.
  # https://github.com/actions/runner-images#available-images
  patches = (old.patches or [ ]) ++ [ ./actionlint-ubuntu-2604.patch ];
})
