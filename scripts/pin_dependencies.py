#
#  pin_dependencies.py
#
#  Created by Grant Brooks Goodman.
#  Copyright © NEOTechnica Corporation. All rights reserved.
#

"""
Rewrites a package manifest so that the branch-based dependencies
owned by an account require that package's latest version tag
instead.

Use this script to produce the manifest for a release commit.
For every `.package(url:branch:)` entry whose URL belongs to the
owner, it replaces the `branch:` requirement with `exact:` and
the highest `v*` tag that the dependency's remote serves.
Entries for other owners, and entries that already use a version
requirement, are left unchanged. A dependency without a version
tag is left on its branch and reported.

Invoke it with the owner and the manifest path:

```
python3 pin_dependencies.py --owner grantbrooksgoodman Package.swift
```

The script rewrites the manifest in place and prints one line
per owned dependency: the package name followed by the pinned
version, or by `unpinned` when the dependency has no version
tag.

> Important: The remote of every owned dependency must be
> readable by the account that runs the script.
"""

# Native
import argparse
from dataclasses import dataclass
import re
import subprocess

PACKAGE_CALL = ".package("
REQUIREMENT_PATTERN = re.compile(r'branch:\s*"[^"]*"')
TAG_PATTERN = re.compile(r"refs/tags/v?(\d+)\.(\d+)\.(\d+)$")
URL_PATTERN = re.compile(
    r'url:\s*"([^"]*[/:]([^/"]+)/([^/"]+?)(?:\.git)?)"'
)

@dataclass(frozen=True)
class _Dependency:
    end: int
    name: str
    owner: str
    start: int
    url: str

@dataclass(frozen=True, order=True)
class _Version:
    # MARK: - Properties

    major: int
    minor: int
    patch: int

    # MARK: - Methods

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

def _call_end(manifest: str, start: int) -> int:
    depth = 0

    for index in range(
        start,
        len(manifest)
    ):
        if manifest[index] == "(":
            depth += 1
        elif manifest[index] == ")":
            depth -= 1
            if depth == 0: return index + 1

    return len(manifest)

def _dependencies(manifest: str) -> list[_Dependency]:
    found: list[_Dependency] = []
    start = manifest.find(PACKAGE_CALL)

    while start != -1:
        end = _call_end(
            manifest,
            start
        )

        match = URL_PATTERN.search(manifest[start:end])

        if match is not None:
            found.append(
                _Dependency(
                    end=end,
                    name=match.group(3),
                    owner=match.group(2),
                    start=start,
                    url=match.group(1)
                )
            )

        start = manifest.find(
            PACKAGE_CALL,
            end
        )

    return found

def _is_branch_based(manifest: str, dependency: _Dependency) -> bool:
    return (REQUIREMENT_PATTERN.search(
        manifest[dependency.start:dependency.end]
    ) is not None)

def _latest_version(url: str) -> _Version | None:
    return max(
        _versions(url),
        default=None
    )

def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument(
        "--owner",
        required=True
    )

    return parser.parse_args()

def _pinned(
    manifest: str,
    dependency: _Dependency,
    version: _Version
) -> str:
    return (
        manifest[:dependency.start]
        + REQUIREMENT_PATTERN.sub(
            f'exact: "{version}"',
            manifest[dependency.start:dependency.end],
            count=1
        )
        + manifest[dependency.end:]
    )

def _tag_listing(url: str) -> str:
    return (
        subprocess
        .run(
            ["git", "ls-remote", "--tags", url],
            capture_output=True,
            check=True,
            text=True
        )
        .stdout
    )

def _versions(url: str) -> list[_Version]:
    versions: list[_Version] = []

    for entry in _tag_listing(url).split():
        match = TAG_PATTERN.search(entry)
        if match is None: continue

        versions.append(
            _Version(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3))
            )
        )

    return versions

def main() -> None:
    """
    Rewrites the manifest named on the command line and prints
    one line per owned dependency.
    """
    arguments = _parse_arguments()
    report: list[str] = []

    with open(
        arguments.manifest,
        encoding="utf-8",
        newline=""
    ) as file:
        manifest = file.read()

    for dependency in reversed(_dependencies(manifest)):
        if (dependency.owner != arguments.owner
                or not _is_branch_based(
                    manifest,
                    dependency
                )):
            continue

        version = _latest_version(dependency.url)

        if version is None:
            report.append(f"{dependency.name} unpinned")
            continue

        manifest = _pinned(
            manifest,
            dependency,
            version
        )

        report.append(f"{dependency.name} {version}")

    with open(
        arguments.manifest,
        "w",
        encoding="utf-8",
        newline=""
    ) as file:
        file.write(manifest)

    for line in sorted(report):
        print(line)

if __name__ == "__main__":
    main()
