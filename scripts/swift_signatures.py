#
#  swift_signatures.py
#
#  Created by Grant Brooks Goodman.
#  Copyright © NEOTechnica Corporation. All rights reserved.
#

"""
Normalizes Swift declaration signatures and decides where a
signature that spans several lines ends.

Use ``terminator_position()`` to find the brace or assignment
that ends a signature, ``continues()`` to decide whether the
signature carries on to the next line, and ``normalized()`` to
produce the canonical text that the API listings compare.
"""

# Native
import re

ACCESS_LEVELS = (
    "fileprivate",
    "internal",
    "open",
    "package",
    "private",
    "public"
)
CONTINUATION_PREFIXES = (
    ")",
    ",",
    "->",
    ":",
    "=",
    ">",
    "async",
    "rethrows",
    "throws",
    "where",
    "{"
)
CONTINUATION_SUFFIXES = (
    "(",
    ",",
    "->",
    ":",
    "<",
    "=",
    "[",
    "where"
)
OPERATORS = (
    "->",
    "<=",
    "==",
    ">="
)
PUNCTUATION_PATTERN = re.compile(r"\s*([(),:\[\]<>?])\s*")
SETTER_MODIFIERS = (
    "fileprivate(set)",
    "internal(set)",
    "package(set)",
    "private(set)"
)
WHITESPACE_PATTERN = re.compile(r"\s+")

def _has_open_bracket(text: str) -> bool:
    depth = 0

    for character in text.replace(
        "->",
        "  "
    ):
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1

    return depth > 0

def _without_operators(text: str) -> str:
    result = text

    for operator in OPERATORS:
        result = result.replace(
            operator,
            "  "
        )

    return result

def continues(text: str, following: str) -> bool:
    """
    Returns a Boolean value that indicates whether a signature
    continues onto the next line.

    - Parameters:
      - text: The signature collected so far, without trailing
        whitespace.
      - following: The next line of source, without surrounding
        whitespace.

    - Returns: `True` if the signature ends with a token that
      requires continuation, contains an unclosed bracket, or
      if the next line begins with a continuation token;
      otherwise, `False`.
    """
    return (text.endswith(CONTINUATION_SUFFIXES)
            or _has_open_bracket(text)
            or following.startswith(CONTINUATION_PREFIXES))

def explicit_access(modifiers: list[str]) -> str | None:
    """
    Returns the access modifier among the given modifiers, if
    any.

    - Parameter modifiers: The modifiers written before the
      declaration keyword.

    - Returns: The last access modifier in the list, or `None`
      if the declaration has no explicit access modifier.
    """
    explicit = None

    for modifier in modifiers:
        if modifier in ACCESS_LEVELS: explicit = modifier

    return explicit

def normalized(
    pending_attributes: str,
    attributes: str,
    modifiers: list[str],
    signature: str
) -> str:
    """
    Returns the canonical text for a declaration.

    The result collapses whitespace, removes the spaces around
    punctuation, and drops access modifiers. An `open`
    declaration is prefixed with `open`, and a declaration whose
    setter is less visible than its getter is prefixed with
    `readonly`.

    - Parameters:
      - pending_attributes: Attributes written on the lines
        above the declaration.
      - attributes: Attributes written on the declaration's
        line.
      - modifiers: The modifiers written before the declaration
        keyword.
      - signature: The declaration text from its keyword to its
        terminator.

    - Returns: The normalized declaration text.
    """
    kept = [
        modifier
        for modifier in modifiers
        if modifier not in ACCESS_LEVELS
        and not modifier.startswith(SETTER_MODIFIERS)
    ]

    text = PUNCTUATION_PATTERN.sub(
        r"\1",
        WHITESPACE_PATTERN.sub(
            " ",
            " ".join([
                pending_attributes,
                attributes,
                " ".join(kept),
                signature
            ])
        ).strip()
    )

    if any(modifier.startswith(SETTER_MODIFIERS) for modifier in modifiers):
        text = "readonly " + text

    if explicit_access(modifiers) == "open": text = "open " + text
    return text

def terminator_position(signature: str) -> int | None:
    """
    Returns the position of the brace or assignment that ends
    the given signature.

    Arrow and comparison operators are ignored so that their
    angle brackets do not affect bracket nesting.

    - Parameter signature: The declaration text collected so
      far.

    - Returns: The index of the first `{` or `=` outside any
      brackets, or `None` if the signature has no terminator
      yet.
    """
    depth = 0

    for position, character in enumerate(_without_operators(signature)):
        if character in "([<":
            depth += 1
        elif character in ")]>":
            depth -= 1
        elif (depth <= 0
              and character in "{="):
            return position

    return None
