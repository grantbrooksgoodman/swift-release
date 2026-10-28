#
#  swift_declarations.py
#
#  Created by Grant Brooks Goodman.
#  Copyright © NEOTechnica Corporation. All rights reserved.
#

"""
Scans Swift source text for declarations and reports each one
together with the type path that encloses it.

Use ``declarations()`` to list the declarations in a file, then
read ``Declaration.is_public`` to find the ones that belong to
the package's public API. The scanner recognizes `public` and
`open` declarations, members of `public` extensions,
requirements of `public` protocols, and cases of `public`
enums.

> Important: The scanner reads the source textually rather
> than compiling it. A declaration that is formatted in an
> unusual way can be reported with a different normalized
> signature, and a member of a `public` extension is reported
> as public even when the extended type is not.
"""

# Native
from dataclasses import dataclass, replace
import re

# Proprietary
from swift_lexing import without_comments_and_strings
from swift_signatures import (
    ACCESS_LEVELS,
    continues,
    explicit_access,
    normalized,
    terminator_position
)

ATTRIBUTE_ONLY_PATTERN = re.compile(
    r"^\s*(@[A-Za-z_][A-Za-z0-9_]*(\([^)]*\))?\s*)+$"
)
KEYWORDS = (
    "actor",
    "associatedtype",
    "case",
    "class",
    "deinit",
    "enum",
    "extension",
    "func",
    "init",
    "let",
    "macro",
    "protocol",
    "struct",
    "subscript",
    "typealias",
    "var"
)
MODIFIERS = (
    "borrowing",
    "class",
    "consuming",
    "convenience",
    "distributed",
    "dynamic",
    "final",
    "indirect",
    "infix",
    "isolated",
    "lazy",
    "mutating",
    r"nonisolated(?:\([^)]*\))?",
    "nonmutating",
    "optional",
    "override",
    "postfix",
    "prefix",
    "required",
    "static",
    r"unowned(?:\([^)]*\))?",
    "weak"
)
DECLARATION_PATTERN = re.compile(
    r"^\s*((?:@[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s+)*)"
    rf"((?:(?:{'|'.join(ACCESS_LEVELS)})(?:\(set\))?\s+"
    rf"|(?:{'|'.join(MODIFIERS)})\s+)*)"
    rf"({'|'.join(KEYWORDS)})\b(.*)$"
)
TYPE_KEYWORDS = (
    "actor",
    "class",
    "enum",
    "extension",
    "protocol",
    "struct"
)
TYPE_NAME_PATTERN = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_.]*)")

@dataclass(frozen=True)
class Declaration:
    """
    A declaration found in Swift source text, together with the
    names of the types that enclose it.

    The scanner produces one ``Declaration`` for every
    declaration it recognizes, whether or not the declaration is
    public. Use ``is_public`` to select the ones that belong to
    the package's public API.
    """

    explicit_access: str | None
    """The access modifier written on the declaration, if any."""

    is_public: bool
    """
    A Boolean value that indicates whether the declaration is
    visible outside the module.
    """

    keyword: str
    """The declaration keyword, such as `func` or `struct`."""

    path: tuple[str, ...]
    """The names of the enclosing types, outermost first."""

    signature: str
    """
    The normalized declaration text, with whitespace collapsed
    and access modifiers removed. An `open` declaration is
    prefixed with `open`, and a declaration whose setter is less
    visible than its getter is prefixed with `readonly`.
    """

@dataclass(frozen=True)
class _Frame:
    depth: int
    is_public: bool
    keyword: str
    member_default_is_public: bool
    name: str

class _FileScanner:
    # MARK: - Properties

    _declarations: list[Declaration]
    _depth: int
    _frames: list[_Frame]
    _lines: list[str]
    _pending_attributes: str

    # MARK: - Init

    def __init__(self, source: str) -> None:
        self._declarations = []
        self._depth = 0
        self._frames = []
        self._lines = without_comments_and_strings(source).split("\n")
        self._pending_attributes = ""

    # MARK: - Methods

    def scan(self) -> list[Declaration]:
        index = 0

        while index < len(self._lines):
            index = self._scan_line(index) + 1

        return self._declarations

    # MARK: - Auxiliary

    def _advance_braces(
        self,
        start: int,
        end: int,
        pending: _Frame | None
    ) -> None:
        for line in self._lines[start:end + 1]:
            for character in line:
                if character == "{":
                    pending = self._open_brace(pending)
                elif character == "}":
                    self._close_brace()

    def _body_depth(self) -> int:
        return self._frames[-1].depth if self._frames else 0

    def _close_brace(self) -> None:
        self._depth -= 1

        while (self._frames
                and self._frames[-1].depth > self._depth):
            self._frames.pop()

    def _collect_signature(
        self,
        index: int,
        text: str
    ) -> tuple[int, str]:
        signature = text
        last = index

        while True:
            terminator = terminator_position(signature)

            if terminator is not None:
                return last, signature[:terminator]

            stripped = signature.rstrip()
            following = self._line_after(last)

            if (last + 1 >= len(self._lines)
                    or not continues(
                        stripped,
                        following
                    )):
                return last, signature

            last += 1
            signature = stripped + " " + following

    def _is_public(
        self,
        keyword: str,
        explicit: str | None
    ) -> bool:
        if explicit is not None:
            is_public = explicit in ("open", "public")
        elif keyword == "case":
            is_public = bool(self._frames) and self._frames[-1].is_public
        else:
            is_public = (bool(self._frames)
                         and self._frames[-1].member_default_is_public)

        return is_public and all(frame.is_public for frame in self._frames)

    def _line_after(self, index: int) -> str:
        if index + 1 >= len(self._lines): return ""
        return self._lines[index + 1].strip()

    def _match_declaration(self, line: str) -> re.Match[str] | None:
        match = DECLARATION_PATTERN.match(line)

        if (match is None
                or self._depth != self._body_depth()):
            return None

        if match.group(3) != "case": return match

        if (not self._frames
                or self._frames[-1].keyword != "enum"):
            return None

        return match

    def _note_attributes(self, line: str) -> None:
        if ATTRIBUTE_ONLY_PATTERN.match(line):
            self._pending_attributes += " " + line.strip()
        elif line.strip():
            self._pending_attributes = ""

    def _open_brace(self, pending: _Frame | None) -> _Frame | None:
        self._depth += 1
        if pending is None: return None

        self._frames.append(
            replace(
                pending,
                depth=self._depth
            )
        )

        return None

    def _pending_frame(
        self,
        keyword: str,
        rest: str,
        explicit: str | None,
        is_public: bool
    ) -> _Frame | None:
        if keyword not in TYPE_KEYWORDS: return None

        name_match = TYPE_NAME_PATTERN.match(rest)

        if keyword == "extension":
            member_default_is_public = explicit in ("open", "public")
        elif keyword == "protocol":
            member_default_is_public = is_public
        else:
            member_default_is_public = False

        return _Frame(
            depth=0,
            is_public=keyword == "extension" or is_public,
            keyword=keyword,
            member_default_is_public=member_default_is_public,
            name=name_match.group(1) if name_match else "?"
        )

    def _scan_line(self, index: int) -> int:
        line = self._lines[index]
        match = self._match_declaration(line)

        if match is None:
            self._note_attributes(line)
            self._advance_braces(
                index,
                index,
                None
            )

            return index

        keyword = match.group(3)
        last, signature = self._collect_signature(
            index,
            keyword + match.group(4)
        )

        modifiers = match.group(2).split()
        explicit = explicit_access(modifiers)
        is_public = self._is_public(
            keyword,
            explicit
        )

        self._declarations.append(
            Declaration(
                explicit_access=explicit,
                is_public=is_public,
                keyword=keyword,
                path=tuple(frame.name for frame in self._frames),
                signature=normalized(
                    self._pending_attributes,
                    match.group(1),
                    modifiers,
                    signature
                )
            )
        )

        self._pending_attributes = ""
        self._advance_braces(
            index,
            last,
            self._pending_frame(
                keyword,
                match.group(4),
                explicit,
                is_public
            )
        )

        return last

def declarations(source: str) -> list[Declaration]:
    """
    Returns the declarations in the given Swift source text.

    - Parameter source: The contents of a Swift source file.

    - Returns: The declarations in the order in which they
      appear in the source.
    """
    return _FileScanner(source).scan()
