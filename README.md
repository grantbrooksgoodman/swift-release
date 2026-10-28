# swift-release

A composite GitHub Action that turns every push to a Swift package's default
branch into a semantic-version tag plus a GitHub release. The bump is derived
from the package's **public API diff** since the previous tag, so the version
number says something about compatibility rather than about effort.

## Use it from a package repository

Add `.github/workflows/release.yml` to the package:

```yaml
name: Release

on:
  push:
    branches: [main]

permissions:
  contents: write

concurrency:
  group: release
  cancel-in-progress: false

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          fetch-tags: true
      - uses: grantbrooksgoodman/swift-release@main
        with:
          initial-version: "1.0.0"   # tagged as-is on the first run; bumps start on the next push
```

The first push with the workflow in place tags `HEAD` with `initial-version`.
Every later push compares `HEAD` with the newest `v*` tag reachable from it and
mints the next version. Pushes that land on an already-tagged commit do nothing.

## Rules, in order of precedence

1. **Explicit token** anywhere in a commit message of the push:
   `[major]`, `[minor]`, `[patch]`, or `[skip release]` (skip folds the push into the next release).
2. **Public API diff** (`public`/`open` declarations, including members of
   `public extension`s and cases of public enums):
   removed or changed symbols → **major**; added symbols → **minor**.
   Adding a parameter *with a default value* to an existing function counts as **minor**.
3. **Package.swift** change to `swift-tools-version` or a platform minimum → **major**.
4. No API change but ≥ 1,000 changed lines in the sources → **minor** (SemVer §7 "may").
5. Otherwise → **patch**.

The API extractor is a lightweight text-level approximation, not the compiler.
It can over-report on pure reformatting (for example a reordered generic
clause) or on an attribute change inside a closure type. When that happens,
put `[patch]` or `[minor]` in the commit message, or delete the tag and release
and re-run. It never silently under-reports a removed `public` symbol.

## Inputs

| Input | Required | Default | Purpose |
|---|---|---|---|
| `initial-version` | yes | — | Version to tag when no `v*` tag exists yet |
| `source-paths` | no | `Sources` | Space-separated paths holding the Swift sources |
| `token` | no | `github.token` | Token with `contents: write` |

## Outputs

`bump` (`major`/`minor`/`patch`/`none`/`seed`/`tagged`) and `version` (no `v` prefix).

## Layout

```
action.yml             the composite action
scripts/public_api.py  dumps the public API surface of a git revision
scripts/api_diff.py    diffs two dumps, recognising defaulted-parameter extensions
scripts/decide_bump.py applies the rules above and prints bump= / version=
```

Everything runs on `ubuntu-latest` with the preinstalled `python3`, `git` and `gh`.
No Swift toolchain is required.
