{
  perSystem.treefmt.programs.oxfmt = {
    enable = true;
    # dprint owns prose/data; djlint owns standalone HTML templates.
    includes = [
      "*.js"
      "*.jsx"
      "*.mjs"
      "*.cjs"
      "*.ts"
      "*.tsx"
      "*.css"
      "*.scss"
      "*.vue"
      "*.graphql"
      "*.mdx"
      "*.yaml"
      "*.yml"
    ];
  };
}
