# swift-release

Mints a semantic version tag and a GitHub release for every
push to a Swift package's default branch.

## Overview

Use `swift-release` to version a Swift package without editing
version numbers by hand. The action compares the package's
public API with the API at the previous tag and derives the
bump from the difference, so a version number describes
compatibility rather than effort.

The action is designed for GitHub's `ubuntu-latest` runner,
which provides the `git`, `gh`, and `python3` tools that it
uses. It does not require a Swift toolchain.

## Adding the workflow

Add `.github/workflows/release.yml` to the package:

```yaml
#
#  release.yml
#
#  Created by Grant Brooks Goodman.
#  Copyright © NEOTechnica Corporation. All rights reserved.
#

# Mints a semantic version tag and a GitHub release for every
# push to a Swift package's default branch. The rules are
# documented at https://github.com/grantbrooksgoodman/swift-release.

name: Release

on:
  push:
    branches: [main]

permissions:
  contents: write

concurrency:
  cancel-in-progress: false
  group: release

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
          initial-version: "1.0.0"
```

The first push with the workflow in place tags the pushed
commit with `initial-version`. Every later push compares the
pushed commit with the newest version tag reachable from it and
mints the next version. A push that lands on an already tagged
commit does nothing.

## How the bump is chosen

The action applies the first rule that matches:

1. An explicit token in any commit message of the push –
   `[major]`, `[minor]`, `[patch]`, or `[skip release]` – sets
   the bump directly. `[skip release]` folds the push into the
   next release.
2. A removed or changed `public` or `open` declaration bumps
   the major version. Members of `public` extensions,
   requirements of `public` protocols, and cases of `public`
   enums are part of the public API.
3. A change to `swift-tools-version` or to a platform minimum
   in `Package.swift` bumps the major version.
4. An added `public` or `open` declaration bumps the minor
   version. Adding a parameter that has a default value to an
   existing function counts as an addition.
5. A change of 1,000 or more lines in the source paths and
   `Package.swift`, with no change to the public API, bumps the
   minor version.
6. Any other change bumps the patch version.

> Important: The action reads declarations textually rather
> than compiling the package. Reformatting a declaration, or
> changing an attribute inside a closure type, can register as
> a removal. Add `[patch]` or `[minor]` to the commit message
> to override the result, or delete the tag and the release and
> run the workflow again.

## History rewrites

Squashing, rebasing, or force-pushing the default branch is
supported. On the next run, every version whose commit is no
longer on the branch is retired: its GitHub release and tag are
deleted. The rewritten head then receives a fresh version that
is higher than every retired version, so numbers never go
backwards and are never reused. Gaps can appear, for example
`v31.0.0` followed by `v31.0.3`.

A commit, push, squash, and force-push sequence triggers two
runs. Any version that the first run mints on the commit before
the squash is retired by the second run, which mints the
squashed commit.

> Note: If a consumer has already resolved a retired version,
> run package resolution again.

## Inputs

| Input | Required | Default | Description |
|---|---|---|---|
| `initial-version` | Yes | – | The version to tag, without a bump, when the repository has no version tag yet. |
| `source-paths` | No | `Sources` | The space-separated paths that hold the package's Swift sources. |
| `token` | No | `github.token` | A token with write access to the repository's contents. |

## Outputs

| Output | Description |
|---|---|
| `bump` | The bump that was applied: `major`, `minor`, `patch`, `none`, `seed`, or `tagged`. |
| `version` | The version that was tagged, without the `v` prefix, or an empty string when nothing was tagged. |

## Files

| File | Purpose |
|---|---|
| `action.yml` | The composite action. |
| `scripts/api_diff.py` | Compares two API listings and reports removed, added, and extended declarations. |
| `scripts/decide_bump.py` | Applies the rules above and prints the bump and the next version. |
| `scripts/public_api.py` | Prints the public API listing of a package at a git revision. |
| `scripts/swift_declarations.py` | Scans Swift source text for declarations. |
| `scripts/swift_lexing.py` | Removes comments and string literals from Swift source text. |
| `scripts/swift_signatures.py` | Normalizes declaration signatures. |

---

&copy; NEOTechnica Corporation. All rights reserved.
