#
#  swift_lexing.py
#
#  Created by Grant Brooks Goodman.
#  Copyright © NEOTechnica Corporation. All rights reserved.
#

"""
Removes comments and string literals from Swift source text so
that braces and keywords can be scanned reliably.

Use ``without_comments_and_strings()`` before scanning source
text for declarations. Line comments are removed, block
comments are removed with their line breaks preserved, and
every string literal is replaced with `""` so that braces
inside interpolations do not affect brace matching.

> Important: Only raw string literals delimited by a single
> `#` are recognized.
"""

def _block_comment_end(
    source: str,
    index: int,
    output: list[str]
) -> int:
    depth = 1
    index += 2

    while (index < len(source)
            and depth):
        if source[index:index + 2] == "/*":
            depth += 1
            index += 2
        elif source[index:index + 2] == "*/":
            depth -= 1
            index += 2
        else:
            if source[index] == "\n": output.append("\n")
            index += 1

    return index

def _line_comment_end(source: str, index: int) -> int:
    end = source.find(
        "\n",
        index
    )

    return len(source) if end == -1 else end

def _multiline_string_end(
    source: str,
    index: int,
    output: list[str]
) -> int:
    end = source.find(
        '"""',
        index + 3
    )

    if end == -1: end = len(source)
    output.append('""')
    output.append("\n" * source[index:end].count("\n"))
    return end + 3

def _raw_string_end(
    source: str,
    index: int,
    output: list[str]
) -> int:
    end = source.find(
        '"#',
        index + 2
    )

    if end == -1: end = len(source)
    output.append('""')
    return end + 2

def _string_end(
    source: str,
    index: int,
    output: list[str]
) -> int:
    end = index + 1

    while end < len(source):
        if source[end] == "\\":
            end += 2
            continue

        if source[end] in '"\n': break
        end += 1

    output.append('""')
    return end + 1

def without_comments_and_strings(source: str) -> str:
    """
    Returns the given Swift source text with comments and
    string literals removed.

    - Parameter source: The contents of a Swift source file.

    - Returns: The source text with each comment removed and
      each string literal replaced with `""`. Line breaks inside
      block comments and multiline string literals are
      preserved.
    """
    output: list[str] = []
    index = 0

    while index < len(source):
        if source[index:index + 2] == "//":
            index = _line_comment_end(
                source,
                index
            )
        elif source[index:index + 2] == "/*":
            index = _block_comment_end(
                source,
                index,
                output
            )
        elif source[index:index + 3] == '"""':
            index = _multiline_string_end(
                source,
                index,
                output
            )
        elif source[index:index + 2] == '#"':
            index = _raw_string_end(
                source,
                index,
                output
            )
        elif source[index] == '"':
            index = _string_end(
                source,
                index,
                output
            )
        else:
            output.append(source[index])
            index += 1

    return "".join(output)
