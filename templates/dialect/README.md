# __PACKAGE_NAME__

This dialect exports the rule module `__MODULE_NAME__` and adds the expression
`answer` to the base grammar. Function syntax and lowering come from `base`.

Run `naru pkg fetch`, then `naru build --locked` using the package-aware launcher.
Keep `Naru.packages.json`, `Naru.packages.lock`, `Naru.toml`, rules, and examples in
version control. `Naru.lock` is the compiler's selected-rule lock; resolve it before
the first locked build. Never commit `.naru` or generated binaries.

For a new language, replace the example rules and choose its own entry, frontend,
analysis/lowering relation, and MLIR pipeline in `Naru.toml`. Dependency installation
does not impose base syntax or LLVM on an independent dialect.

To register a release, add this package identity and a stable version to a JSON
registry with a Git repository URL, revision, and optional package subdirectory.
The registry version must match `[package].version`. The client pins the resulting
commit and content when it resolves dependencies; it never runs package scripts.
