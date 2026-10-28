#!/usr/bin/env python3
"""Approximate public-API surface extractor for a Swift package tree at a git revision.

Usage: public_api.py <repo> <rev> [source paths…]  -> prints one signature per line (sorted). Default source path: Sources
"""
import re, subprocess, sys

TYPE_KW = ('struct', 'class', 'enum', 'actor', 'protocol', 'extension')
MEMBER_KW = ('func', 'var', 'let', 'init', 'subscript', 'typealias', 'associatedtype', 'case', 'macro', 'deinit')
ACCESS = ('open', 'public', 'package', 'internal', 'fileprivate', 'private')
MODIFIERS = ('final', 'static', 'class', 'nonisolated', 'override', 'mutating', 'nonmutating', 'unowned', 'weak',
             'lazy', 'indirect', 'convenience', 'required', 'dynamic', 'optional', 'prefix', 'postfix', 'infix',
             'unowned(safe)', 'unowned(unsafe)', 'isolated', 'distributed', 'consuming', 'borrowing')

def strip_comments_and_strings(src: str) -> str:
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith('//', i):
            j = src.find('\n', i)
            if j == -1: j = n
            i = j
            continue
        if src.startswith('/*', i):
            depth = 1; i += 2
            while i < n and depth:
                if src.startswith('/*', i): depth += 1; i += 2
                elif src.startswith('*/', i): depth -= 1; i += 2
                else:
                    if src[i] == '\n': out.append('\n')
                    i += 1
            continue
        if src.startswith('"""', i):
            j = src.find('"""', i + 3)
            if j == -1: j = n
            out.append('""'); 
            out.append('\n' * src[i:j].count('\n'))
            i = j + 3
            continue
        if c == '"' or (c == '#' and src.startswith('#"', i)):
            if c == '#':
                m = re.match(r'#+"', src[i:])
                hashes = m.group(0)[:-1]
                close = '"' + hashes
                j = src.find(close, i + len(hashes) + 1)
                if j == -1: j = n
                out.append('""'); i = j + len(close); continue
            j = i + 1
            while j < n:
                if src[j] == '\\': j += 2; continue
                if src[j] == '"': break
                if src[j] == '\n': break
                j += 1
            out.append('""'); i = j + 1
            continue
        out.append(c); i += 1
    return ''.join(out)

def access_of(words):
    for w in words:
        if w in ACCESS: return w
        if w.startswith('private(set)') or w.startswith('fileprivate(set)') or w.startswith('internal(set)') or w.startswith('package(set)'):
            continue
    return None

decl_re = re.compile(
    r'^\s*((?:@[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s+)*)'   # attributes
    r'((?:(?:open|public|package|internal|fileprivate|private)(?:\(set\))?\s+|(?:final|static|class|nonisolated(?:\([^)]*\))?|override|mutating|nonmutating|unowned(?:\([^)]*\))?|weak|lazy|indirect|convenience|required|dynamic|optional|prefix|postfix|infix|isolated|distributed|consuming|borrowing)\s+)*)'  # modifiers
    r'(struct|class|enum|actor|protocol|extension|func|var|let|init|subscript|typealias|associatedtype|case|macro|deinit)\b(.*)$'
)
attr_only_re = re.compile(r'^\s*(@[A-Za-z_][A-Za-z0-9_]*(\([^)]*\))?\s*)+$')

def extract(src: str):
    """Return list of (path_tuple, effective_public, kind, sigtext) for every declaration."""
    text = strip_comments_and_strings(src)
    lines = text.split('\n')
    results = []
    frames = []        # list of dicts: depth, kind, name, access(effective default for members: 'public' or None)
    depth = 0
    pending_attrs = ''
    i = 0
    nlines = len(lines)
    while i < nlines:
        line = lines[i]
        m = decl_re.match(line)
        consumed_to = i
        if m and not line.strip().startswith('case ') or (m and m.group(3) == 'case'):
            attrs, mods, kw, rest = m.group(1), m.group(2), m.group(3), m.group(4)
            # 'case' inside a switch statement vs enum: only treat as enum case when directly inside enum frame
            if kw == 'case':
                if not frames or frames[-1]['kind'] not in ('enum',) or frames[-1]['depth'] != depth:
                    m = None
            # 'class' as modifier (class func) is handled by regex; 'class' kw here is a type
        if m:
            body_depth = frames[-1]['depth'] if frames else 0
            if depth != body_depth:
                m = None
        if m:
            attrs, mods, kw, rest = m.group(1), m.group(2), m.group(3), m.group(4)
            # gather full signature across lines
            sig = kw + rest
            pdepth = 0
            def upd(s):
                nonlocal pdepth
                s2 = s.replace('->', '  ').replace('==', '  ').replace('<=', '  ').replace('>=', '  ')
                for ch in s2:
                    if ch in '([<': pdepth += 1
                    elif ch in ')]>': pdepth -= 1
            # find terminator in current text at depth 0
            def find_term(s):
                d = 0
                s2 = s.replace('->', '  ').replace('==', '  ').replace('<=', '  ').replace('>=', '  ')
                k = 0
                while k < len(s2):
                    ch = s2[k]
                    if ch in '([<': d += 1
                    elif ch in ')]>': d -= 1
                    elif d <= 0 and ch == '{': return k, '{'
                    elif d <= 0 and ch == '=' and kw not in ('case',): return k, '='
                    elif d <= 0 and ch == '=' and kw == 'case': return k, '='
                    k += 1
                return None, None
            j = i
            full = sig
            while True:
                pos, term = find_term(full)
                if pos is not None:
                    full = full[:pos]
                    break
                # decide whether to continue on next line
                stripped = full.rstrip()
                nxt = lines[j + 1].strip() if j + 1 < nlines else ''
                cont_prev = stripped.endswith((',', '(', '<', ':', '->', '=', 'where', '[')) or pdepth_open(stripped)
                cont_next = nxt.startswith(('->', 'where', 'async', 'throws', 'rethrows', ':', ',', ')', '=', '{', '>'))
                if (cont_prev or cont_next) and j + 1 < nlines:
                    j += 1
                    full = stripped + ' ' + nxt
                else:
                    break
            consumed_to = j
            # effective access
            modwords = mods.split()
            explicit = None
            for w in modwords:
                if w in ACCESS: explicit = w
                elif w.startswith(('private(set)', 'fileprivate(set)', 'internal(set)', 'package(set)')): pass
            enclosing_default = frames[-1]['member_default'] if frames else None
            if explicit:
                eff_public = explicit in ('public', 'open')
            else:
                if kw == 'case':
                    eff_public = bool(frames) and frames[-1]['eff_public']
                else:
                    eff_public = enclosing_default == 'public'
            # also require all enclosing frames to be effectively public
            if eff_public and any(not f['eff_public'] for f in frames):
                eff_public = False
            path = tuple(f['name'] for f in frames)
            norm = re.sub(r'\s+', ' ', (pending_attrs + ' ' + attrs + ' ' + ' '.join(w for w in modwords if w not in ACCESS and not w.startswith(('private(set)','fileprivate(set)','internal(set)','package(set)'))) + ' ' + full)).strip()
            # keep explicit setter restrictions as part of signature (public private(set) var is read-only externally)
            setter = [w for w in modwords if w.startswith(('private(set)', 'fileprivate(set)', 'internal(set)', 'package(set)'))]
            norm = re.sub(r'\s*([(),:\[\]<>?])\s*', r'\1', norm)
            if setter: norm = 'readonly ' + norm
            if explicit == 'open': norm = 'open ' + norm
            results.append((path, eff_public, kw, norm, explicit))
            if kw in TYPE_KW:
                name_m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_.]*)', rest)
                name = name_m.group(1) if name_m else '?'
                # member default access for this frame
                if kw == 'extension':
                    member_default = 'public' if explicit in ('public', 'open') else None
                    frame_public = True  # resolved later via type table
                elif kw == 'protocol':
                    member_default = 'public' if eff_public else None
                    frame_public = eff_public
                else:
                    member_default = None
                    frame_public = eff_public
                # the frame opens at the '{' that terminates this declaration; find the depth after that line
                pending_frame = {'kind': kw, 'name': name, 'member_default': member_default, 'eff_public': frame_public,
                                 'explicit': explicit}
                # push now, assign depth when we see '{'
                frames_to_push = pending_frame
            else:
                frames_to_push = None
            pending_attrs = ''
        else:
            frames_to_push = None
            if attr_only_re.match(line):
                pending_attrs += ' ' + line.strip()
            elif line.strip():
                pending_attrs = ''
        # update brace depth over consumed lines
        for k in range(i, consumed_to + 1):
            for ch in lines[k]:
                if ch == '{':
                    depth += 1
                    if frames_to_push is not None:
                        frames_to_push['depth'] = depth
                        frames.append(frames_to_push)
                        frames_to_push = None
                elif ch == '}':
                    depth -= 1
                    while frames and frames[-1]['depth'] > depth:
                        frames.pop()
        i = consumed_to + 1
    return results

def pdepth_open(s):
    d = 0
    s2 = s.replace('->', '  ')
    for ch in s2:
        if ch in '([': d += 1
        elif ch in ')]': d -= 1
    return d > 0

def main():
    repo, rev = sys.argv[1], sys.argv[2]
    paths = sys.argv[3:] or ['Sources']
    files = subprocess.run(['git', '-C', repo, 'ls-tree', '-r', '--name-only', rev, '--', *paths],
                           capture_output=True, text=True, check=True).stdout.split('\n')
    files = [f for f in files if f.endswith('.swift')]
    all_decls = []
    for f in files:
        src = subprocess.run(['git', '-C', repo, 'show', f'{rev}:{f}'], capture_output=True, text=True, check=True).stdout
        for d in extract(src):
            all_decls.append((f,) + d)
    # Build type table: name -> effective public (for types declared with struct/class/enum/actor/protocol)
    type_public = {}
    for f, path, pub, kw, norm, explicit in all_decls:
        if kw in ('struct', 'class', 'enum', 'actor', 'protocol'):
            name = norm.split()[-0]
            nm = re.search(r'\b(struct|class|enum|actor|protocol)\s+([A-Za-z_][A-Za-z0-9_]*)', norm)
            if nm:
                full = '.'.join(path + (nm.group(2),))
                type_public[full] = type_public.get(full, False) or pub
                type_public.setdefault(nm.group(2), False)
                type_public[nm.group(2)] = type_public[nm.group(2)] or pub
    # typealiases that are public also count as public type names
    for f, path, pub, kw, norm, explicit in all_decls:
        if kw == 'typealias':
            nm = re.search(r'\btypealias\s+([A-Za-z_][A-Za-z0-9_]*)', norm)
            if nm and pub:
                type_public[nm.group(1)] = True
    out = set()
    # Second pass: resolve extension frames. We need, for each decl, whether every enclosing extension extends a public type.
    # We re-run extraction with knowledge of type_public to decide extension frame publicness.
    def ext_is_public(name):
        # unknown (external module) types are public; internal declared types are not
        if name in type_public: return type_public[name]
        last = name.split('.')[-1]
        if last in type_public: return type_public[last]
        return True
    for f in files:
        src = subprocess.run(['git', '-C', repo, 'show', f'{rev}:{f}'], capture_output=True, text=True, check=True).stdout
        decls = extract(src)
        # reconstruct frame publicness along path: path names only; approximate by checking each name
        for path, pub, kw, norm, explicit in decls:
            if not pub: continue
            ok = True
            for nm in path:
                if not ext_is_public(nm): ok = False; break
            if not ok: continue
            if kw == 'extension':
                # extension itself is not API; skip unless it adds conformances
                nm = re.match(r'extension\s+([A-Za-z_][A-Za-z0-9_.]*)\s*(:\s*(.*))?', norm.split('extension',1)[1].strip() and 'extension'+norm.split('extension',1)[1])
                conf = re.search(r'extension\s+([A-Za-z_][A-Za-z0-9_.<>, ]*?)\s*:\s*([^{]*?)(\s+where\b.*)?$', norm)
                if conf and explicit in ('public', 'open'):
                    out.add(f"{conf.group(1).strip()} :: conforms {conf.group(2).strip()}{(conf.group(3) or '').strip() and ' ' + conf.group(3).strip()}")
                continue
            key = '.'.join(path) + ' :: ' + norm if path else norm
            out.add(key)
    for k in sorted(out):
        print(k)

if __name__ == '__main__':
    main()
