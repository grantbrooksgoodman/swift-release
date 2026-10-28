#!/usr/bin/env python3
"""Compare two public-API dumps produced by public_api.py.

A symbol that disappears but reappears with the same name and a parameter list
that only *adds defaulted parameters* (same types, return type and effects) is
reported as "extended" (backwards compatible), not "removed".

Usage: api_diff.py BEFORE AFTER --out-dir DIR
Prints removed=N added=N extended=N; writes api_removed.txt, api_added.txt, api_extended.txt.
"""
import argparse
import os
import re

ARROW = "→"  # stands in for '->' so its '>' does not confuse depth tracking


def split_top_level(s: str, sep: str = ",") -> list[str]:
    out, depth, cur = [], 0, []
    for ch in s:
        if ch in "([<":
            depth += 1
        elif ch in ")]>":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def parse(sig: str):
    """Return (head, params, defaults, tail) for callable-like signatures, else None."""
    sig = sig.replace("->", ARROW)
    m = re.match(r"^(.*?\b(?:func|init|subscript|case)\b[^(]*)\((.*)$", sig)
    if not m:
        return None
    head, rest = m.group(1), m.group(2)
    depth, i = 1, 0
    while i < len(rest) and depth:
        if rest[i] in "([<":
            depth += 1
        elif rest[i] in ")]>":
            depth -= 1
        i += 1
    params, tail = rest[: i - 1], rest[i:]
    plist, defaults = [], []
    for p in split_top_level(params):
        p = p.strip()
        if not p:
            continue
        plist.append(p)
        defaults.append("=" in p.split(":", 1)[-1] if ":" in p else False)
    return head.strip(), plist, defaults, tail.strip()


def is_extension(old: str, new: str) -> bool:
    """True when `new` only inserts defaulted parameters into `old`."""
    po, pn = parse(old), parse(new)
    if not po or not pn or po[0] != pn[0] or po[3] != pn[3]:
        return False
    old_params, new_params, new_defaults = po[1], pn[1], pn[2]
    j = 0
    for i, param in enumerate(new_params):
        if j < len(old_params) and param == old_params[j]:
            j += 1
        elif not new_defaults[i]:
            return False
    return j == len(old_params) and len(new_params) > len(old_params)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out-dir", default=".")
    a = ap.parse_args()
    before = set(open(a.before).read().splitlines())
    after = set(open(a.after).read().splitlines())
    removed = sorted(before - after)
    added = sorted(after - before)
    extended = []
    for old in list(removed):
        for new in added:
            if is_extension(old, new):
                extended.append(f"{old}\n  -> {new}")
                removed.remove(old)
                added.remove(new)
                break
    os.makedirs(a.out_dir, exist_ok=True)
    for name, items in (("removed", removed), ("added", added), ("extended", extended)):
        with open(os.path.join(a.out_dir, f"api_{name}.txt"), "w") as f:
            f.write("\n".join(items) + ("\n" if items else ""))
    print(f"removed={len(removed)}")
    print(f"added={len(added)}")
    print(f"extended={len(extended)}")


if __name__ == "__main__":
    main()
