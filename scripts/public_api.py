#
#  public_api.py
#
#  Created by Grant Brooks Goodman.
#  Copyright © NEOTechnica Corporation. All rights reserved.
#

"""
Prints the public API surface of a Swift package at a git
revision, one declaration per line, sorted.

Use this script to compare the API surface of two revisions:
run it once per revision and compare the outputs with
`api_diff.py`. Each line names the enclosing type path and the
normalized declaration, for example
`Logger :: static func setFilter(_ filter:Filter?)`.

Invoke it with the repository path, the revision, and
optionally the source paths to scan. When no source path is
given, `Sources` is scanned:

```
python3 public_api.py /path/to/package v1.2.3 Sources
```

> Important: A member of an extension is listed only when the
> extended type is public or is declared outside the package.
"""

# Native
import re
import subprocess
import sys

# Proprietary
from swift_declarations import Declaration, declarations

CONFORMANCE_PATTERN = re.compile(
    r"extension\s+([A-Za-z_][A-Za-z0-9_.<>, ]*?)\s*:\s*([^{]*?)(\s+where\b.*)?$"
)
DEFAULT_SOURCE_PATHS = ("Sources",)
NAMED_TYPE_KEYWORDS = (
    "actor",
    "class",
    "enum",
    "protocol",
    "struct"
)
NAMED_TYPE_PATTERN = re.compile(
    rf"\b({'|'.join(NAMED_TYPE_KEYWORDS)})\s+([A-Za-z_][A-Za-z0-9_]*)"
)
TYPEALIAS_PATTERN = re.compile(r"\btypealias\s+([A-Za-z_][A-Za-z0-9_]*)")

def _conformance_line(declaration: Declaration) -> str | None:
    if declaration.explicit_access not in ("open", "public"): return None

    match = CONFORMANCE_PATTERN.search(declaration.signature)
    if match is None: return None

    line = f"{match.group(1).strip()} :: conforms {match.group(2).strip()}"
    where_clause = (match.group(3) or "").strip()
    if where_clause: line += " " + where_clause
    return line

def _declarations_at(
    repository: str,
    revision: str,
    paths: list[str]
) -> list[Declaration]:
    found: list[Declaration] = []

    for path in _swift_files(
        repository,
        revision,
        paths
    ):
        found.extend(
            declarations(
                _git(
                    repository,
                    "show",
                    f"{revision}:{path}"
                )
            )
        )

    return found

def _git(repository: str, *arguments: str) -> str:
    return (
        subprocess
        .run(
            ["git", "-C", repository, *arguments],
            capture_output=True,
            check=True,
            text=True
        )
        .stdout
    )

def _is_public_type_name(
    name: str,
    public_types: dict[str, bool]
) -> bool:
    if name in public_types: return public_types[name]

    return public_types.get(
        name.split(".")[-1],
        True
    )

def _public_surface(
    repository: str,
    revision: str,
    paths: list[str]
) -> list[str]:
    found = _declarations_at(
        repository,
        revision,
        paths
    )

    public_types = _public_type_names(found)
    surface: set[str] = set()

    for declaration in found:
        if (not declaration.is_public
                or not all(
                    _is_public_type_name(
                        name,
                        public_types
                    )
                    for name in declaration.path
                )):
            continue

        if declaration.keyword == "extension":
            line = _conformance_line(declaration)
            if line is not None: surface.add(line)
            continue

        surface.add(_surface_line(declaration))

    return sorted(surface)

def _public_type_names(found: list[Declaration]) -> dict[str, bool]:
    public_types: dict[str, bool] = {}

    for declaration in found:
        if declaration.keyword in NAMED_TYPE_KEYWORDS:
            match = NAMED_TYPE_PATTERN.search(declaration.signature)
            if match is None: continue

            name = match.group(2)
            qualified = ".".join(declaration.path + (name,))
            public_types[qualified] = (
                public_types.get(
                    qualified,
                    False
                )
                or declaration.is_public
            )

            public_types[name] = (
                public_types.get(
                    name,
                    False
                )
                or declaration.is_public
            )
        elif (declaration.keyword == "typealias"
                and declaration.is_public):
            match = TYPEALIAS_PATTERN.search(declaration.signature)
            if match is not None: public_types[match.group(1)] = True

    return public_types

def _surface_line(declaration: Declaration) -> str:
    if not declaration.path: return declaration.signature
    return ".".join(declaration.path) + " :: " + declaration.signature

def _swift_files(
    repository: str,
    revision: str,
    paths: list[str]
) -> list[str]:
    return [
        path
        for path in _git(
            repository,
            "ls-tree",
            "-r",
            "--name-only",
            revision,
            "--",
            *paths
        )
        .split("\n")
        if path.endswith(".swift")
    ]

def main() -> None:
    """
    Prints the public API surface for the revision named on the
    command line.

    The first argument is the repository path and the second is
    the revision. Any further arguments are the source paths to
    scan; when none is given, `Sources` is scanned.
    """
    if len(sys.argv) < 3:
        sys.exit("usage: public_api.py <repository> <revision> [path …]")

    for line in _public_surface(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3:] or list(DEFAULT_SOURCE_PATHS)
    ):
        print(line)

if __name__ == "__main__":
    main()
