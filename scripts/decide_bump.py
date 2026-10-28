#
#  decide_bump.py
#
#  Created by Grant Brooks Goodman.
#  Copyright © NEOTechnica Corporation. All rights reserved.
#

"""
Decides the next semantic version for a push to a package's
default branch and prints it for `$GITHUB_OUTPUT`.

The script applies the first rule that matches:

1. An explicit token in any commit message of the push –
   `[major]`, `[minor]`, `[patch]`, or `[skip release]` – sets
   the bump directly. `[skip release]` folds the push into the
   next release.
2. A removed or changed public declaration bumps the major
   version.
3. A change to `swift-tools-version` or to a platform minimum
   in `Package.swift` bumps the major version.
4. An added public declaration bumps the minor version.
5. A change of 1,000 or more lines with no change to the public
   API bumps the minor version.
6. Any other change bumps the patch version.

Pass `--seed` instead of `--prev` when no version tag is
reachable from `HEAD`; the result is then the seed version
itself. Pass `--floor` with the highest version that a history
rewrite retired; the result is raised to the next patch version
above the floor when it would otherwise not exceed it.

Invoke it with the counts gathered by the action:

```
python3 decide_bump.py --prev v1.2.3 --removed 0 --added 2
```

The script prints `bump=` and `version=` lines. The version is
empty when the bump is `none`.
"""

# Native
import argparse
from dataclasses import dataclass
import re
import sys

MINOR_LINE_THRESHOLD = 1000
SKIP_TOKEN = "[skip release]"
# Ordered by precedence: the first token found decides the bump.
TOKENS = (
    ("[major]", "major"),
    ("[minor]", "minor"),
    ("[patch]", "patch")
)
VERSION_PATTERN = re.compile(r"v?(\d+)\.(\d+)\.(\d+)$")

@dataclass(frozen=True, order=True)
class _Version:
    # MARK: - Properties

    major: int
    minor: int
    patch: int

    # MARK: - Methods

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bumped(self, level: str) -> "_Version":
        if level == "major":
            return _Version(
                self.major + 1,
                0,
                0
            )

        if level == "minor":
            return _Version(
                self.major,
                self.minor + 1,
                0
            )

        if level == "patch":
            return _Version(
                self.major,
                self.minor,
                self.patch + 1
            )

        return self

    @classmethod
    def parse(cls, text: str) -> "_Version":
        match = VERSION_PATTERN.match(text.strip())

        if match is None:
            sys.exit(f"cannot parse version {text!r}")

        return cls(*(int(group) for group in match.groups()))

def _decide(arguments: argparse.Namespace) -> tuple[str, str]:
    messages = arguments.messages.lower()

    for token, level in TOKENS:
        if token in messages: return level, f"explicit {token} token"

    if SKIP_TOKEN in messages: return "none", f"explicit {SKIP_TOKEN} token"

    if arguments.removed:
        return (
            "major",
            f"{arguments.removed} public symbol(s) removed or changed"
        )

    if arguments.platform_changed:
        return (
            "major",
            "platform or swift-tools-version requirement changed"
        )

    if arguments.added:
        return "minor", f"{arguments.added} public symbol(s) added"

    if arguments.lines >= MINOR_LINE_THRESHOLD:
        return (
            "minor",
            f"{arguments.lines} changed lines with no public API change"
        )

    return "patch", f"{arguments.lines} changed lines, no public API change"

def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--added",
        default=0,
        type=int
    )

    parser.add_argument(
        "--floor",
        default=""
    )

    parser.add_argument(
        "--lines",
        default=0,
        type=int
    )

    parser.add_argument(
        "--messages",
        default=""
    )

    parser.add_argument(
        "--platform-changed",
        default=0,
        type=int
    )

    parser.add_argument(
        "--prev",
        default=""
    )

    parser.add_argument(
        "--removed",
        default=0,
        type=int
    )

    parser.add_argument(
        "--seed",
        default=""
    )

    return parser.parse_args()

def main() -> None:
    """
    Prints the bump and the next version for the arguments
    given on the command line.
    """
    arguments = _parse_arguments()
    floor = _Version.parse(arguments.floor) if arguments.floor else None

    if arguments.seed:
        bump = "seed"
        reason = "no version tag reachable from HEAD"
        version = _Version.parse(arguments.seed)
    else:
        if not arguments.prev:
            sys.exit("either --prev or --seed is required")

        bump, reason = _decide(arguments)
        version = _Version.parse(arguments.prev).bumped(bump)

    if (floor is not None
            and bump != "none"
            and version <= floor):
        version = floor.bumped("patch")
        reason += f"; raised above retired {arguments.floor}"

    print(
        f"{arguments.prev or arguments.seed} -> {bump}: {reason}",
        file=sys.stderr
    )

    print(f"bump={bump}")
    print(f"version={'' if bump == 'none' else version}")

if __name__ == "__main__":
    main()
