#!/usr/bin/env python3
"""Decide the next semantic version for a push to the default branch.

Precedence:
  1. An explicit token in any commit message of the push: [major] [minor] [patch] [skip release]
  2. Public-API diff (from api_diff.py): removed/changed symbols -> major, added symbols -> minor
  3. Package.swift platform or swift-tools-version change -> major
  4. Large internal change with no API change (>= MINOR_LINE_THRESHOLD changed lines) -> minor
  5. Otherwise -> patch

With --seed INITIAL (no previous tag reachable) the result is INITIAL itself.
With --floor RETIRED (a version retired by a history rewrite) the result is raised
to the next patch above RETIRED when it would otherwise not exceed it.

Prints `bump=…` and `version=…` lines for $GITHUB_OUTPUT.
"""
import argparse
import re
import sys

MINOR_LINE_THRESHOLD = 1000
TOKENS = (("[major]", "major"), ("[minor]", "minor"), ("[patch]", "patch"))
SKIP_TOKEN = "[skip release]"


def parse(tag: str) -> tuple[int, int, int]:
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)$", tag.strip())
    if not m:
        sys.exit(f"cannot parse version {tag!r}")
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--prev", default="", help="previous tag, e.g. v31.0.0")
    p.add_argument("--seed", default="", help="initial version to use when no tag is reachable")
    p.add_argument("--floor", default="", help="highest retired version; the result must exceed it")
    p.add_argument("--removed", type=int, default=0)
    p.add_argument("--added", type=int, default=0)
    p.add_argument("--lines", type=int, default=0, help="changed lines in the sources + Package.swift")
    p.add_argument("--platform-changed", type=int, default=0)
    p.add_argument("--messages", default="")
    a = p.parse_args()

    if a.seed:
        bump, why = "seed", "no version tag reachable from HEAD"
        major, minor, patch = parse(a.seed)
    else:
        if not a.prev:
            sys.exit("either --prev or --seed is required")
        major, minor, patch = parse(a.prev)
        msgs = a.messages.lower()
        bump = None
        why = ""
        for token, level in TOKENS:  # highest level wins if several tokens appear
            if token in msgs:
                bump, why = level, f"explicit {token} token"
                break
        if bump is None and SKIP_TOKEN in msgs:
            bump, why = "none", f"explicit {SKIP_TOKEN} token"
        if bump is None:
            if a.removed:
                bump, why = "major", f"{a.removed} public symbol(s) removed or changed"
            elif a.platform_changed:
                bump, why = "major", "platform or swift-tools-version requirement changed"
            elif a.added:
                bump, why = "minor", f"{a.added} public symbol(s) added"
            elif a.lines >= MINOR_LINE_THRESHOLD:
                bump, why = "minor", f"{a.lines} changed lines with no public API change"
            else:
                bump, why = "patch", f"{a.lines} changed lines, no public API change"
        if bump == "major":
            major, minor, patch = major + 1, 0, 0
        elif bump == "minor":
            minor, patch = minor + 1, 0
        elif bump == "patch":
            patch += 1

    if a.floor and bump != "none" and (major, minor, patch) <= parse(a.floor):
        f = parse(a.floor)
        major, minor, patch = f[0], f[1], f[2] + 1
        why += f"; raised above retired {a.floor}"

    print(f"{a.prev or a.seed} -> {bump}: {why}", file=sys.stderr)
    print(f"bump={bump}")
    if bump == "none":
        print("version=")
    else:
        print(f"version={major}.{minor}.{patch}")


if __name__ == "__main__":
    main()
