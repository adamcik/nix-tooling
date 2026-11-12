{
  perSystem.treefmt.programs.oxfmt = {
    enable = true;
    # rumdl owns Markdown, dprint owns data, and djlint owns standalone HTML.
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
