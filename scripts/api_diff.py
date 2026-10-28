#
#  api_diff.py
#
#  Created by Grant Brooks Goodman.
#  Copyright © NEOTechnica Corporation. All rights reserved.
#

"""
Compares two public API listings produced by `public_api.py`
and reports the declarations that were removed, added, or
extended.

A declaration is extended when it reappears with the same name,
return type, and effects, and its parameter list only gains
parameters that have default values. An extended declaration is
backward compatible, so it is reported separately from a
removed one.

Invoke it with the two listings and an output directory:

```
python3 api_diff.py before.txt after.txt --out-dir DIR
```

The script prints `removed=`, `added=`, and `extended=` counts,
and writes `api_removed.txt`, `api_added.txt`, and
`api_extended.txt` to the output directory.
"""

# Native
import argparse
from dataclasses import dataclass
import os
import re

ARROW = "→"
SIGNATURE_PATTERN = re.compile(
    r"^(.*?\b(?:func|init|subscript|case)\b[^(]*)\((.*)$"
)

@dataclass(frozen=True)
class _Signature:
    defaults: list[bool]
    head: str
    parameters: list[str]
    tail: str

def _has_default(parameter: str) -> bool:
    if ":" not in parameter: return False

    return "=" in parameter.split(
        ":",
        1
    )[-1]

def _is_extension(old: str, new: str) -> bool:
    before = _parse_signature(old)
    after = _parse_signature(new)

    if (before is None
            or after is None
            or before.head != after.head
            or before.tail != after.tail):
        return False

    matched = 0

    for index, parameter in enumerate(after.parameters):
        if (matched < len(before.parameters)
                and parameter == before.parameters[matched]):
            matched += 1
        elif not after.defaults[index]:
            return False

    return (matched == len(before.parameters)
            and len(after.parameters) > len(before.parameters))

def _lines(path: str) -> list[str]:
    with open(
        path,
        encoding="utf-8"
    ) as file:
        return file.read().splitlines()

def _parse_signature(signature: str) -> _Signature | None:
    match = SIGNATURE_PATTERN.match(
        signature.replace(
            "->",
            ARROW
        )
    )

    if match is None: return None

    remainder = match.group(2)
    depth = 1
    index = 0

    while (index < len(remainder)
            and depth):
        if remainder[index] in "([<":
            depth += 1
        elif remainder[index] in ")]>":
            depth -= 1

        index += 1

    parameters = [
        parameter.strip()
        for parameter in _split_top_level(remainder[:index - 1])
        if parameter.strip()
    ]

    return _Signature(
        defaults=[_has_default(parameter) for parameter in parameters],
        head=match.group(1).strip(),
        parameters=parameters,
        tail=remainder[index:].strip()
    )

def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0

    for character in text:
        if character in "([<":
            depth += 1
        elif character in ")]>":
            depth -= 1

        if (character == ","
                and depth == 0):
            parts.append("".join(current))
            current = []
        else:
            current.append(character)

    if current: parts.append("".join(current))
    return parts

def _write(
    directory: str,
    name: str,
    items: list[str]
) -> None:
    with open(
        os.path.join(
            directory,
            f"api_{name}.txt"
        ),
        "w",
        encoding="utf-8"
    ) as file:
        file.write("\n".join(items) + ("\n" if items else ""))

def main() -> None:
    """
    Compares the two listings named on the command line and
    writes the result to the output directory.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument(
        "--out-dir",
        default="."
    )

    arguments = parser.parse_args()
    before = set(_lines(arguments.before))
    after = set(_lines(arguments.after))
    removed = sorted(before - after)
    added = sorted(after - before)
    extended: list[str] = []

    for old in list(removed):
        replacement = next(
            (new for new in added if _is_extension(
                old,
                new
            )),
            None
        )

        if replacement is None: continue
        extended.append(f"{old}\n  -> {replacement}")
        removed.remove(old)
        added.remove(replacement)

    os.makedirs(
        arguments.out_dir,
        exist_ok=True
    )

    _write(
        arguments.out_dir,
        "removed",
        removed
    )

    _write(
        arguments.out_dir,
        "added",
        added
    )

    _write(
        arguments.out_dir,
        "extended",
        extended
    )

    print(f"removed={len(removed)}")
    print(f"added={len(added)}")
    print(f"extended={len(extended)}")

if __name__ == "__main__":
    main()
