#!/usr/bin/env python3
"""Report the LWJGL API a Minecraft version uses that a given LWJGL jar does not provide.

Every class, field, method and lambda reference to org/lwjgl in the client jar and its
libraries is resolved against the given LWJGL jar the way the JVM links it, and everything
that would throw NoClassDefFoundError, NoSuchMethodError, NoSuchFieldError,
IncompatibleClassChangeError, IllegalAccessError or AbstractMethodError is printed, with the
declaration from the LWJGL version Minecraft itself ships for reference.

  lwjgl_compat_check.py --version 26.1 --lwjgl build/lwjgl.jar [--jdk rt.jar]
  lwjgl_compat_check.py --jar client.jar [--jar lib.jar ...] [--ref lwjgl-3.4.1.jar ...] --lwjgl build/lwjgl.jar

Only the Python 3 standard library is used. Downloads are verified against their SHA-1.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys
import urllib.parse
import urllib.request
import zipfile

MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
LWJGL = 'org/lwjgl/'
DESC_CLASS = re.compile(r'L([^;]+);')

ACC_PUBLIC, ACC_PRIVATE, ACC_PROTECTED, ACC_STATIC, ACC_FINAL = 0x1, 0x2, 0x4, 0x8, 0x10
ACC_NATIVE, ACC_INTERFACE, ACC_ABSTRACT = 0x100, 0x200, 0x400

UNKNOWN = object()  # resolution hit a class outside LWJGL that is not indexed


class ClassInfo:
    def __init__(self):
        self.name = None
        self.super = None
        self.access = 0
        self.interfaces = []
        self.fields = {}       # (name, desc) -> (access, ConstantValue or None)
        self.methods = {}      # (name, desc) -> access
        self.class_refs = set()
        self.field_refs = set()     # (owner, name, desc)
        self.method_refs = set()    # (owner, name, desc, is InterfaceMethodref)
        self.lambdas = set()        # (interface, method name, method descriptor)
        self.desc_types = set()     # LWJGL classes named in descriptors only


def lwjgl_types(desc):
    return [c for c in DESC_CLASS.findall(desc) if c.startswith(LWJGL)]


def parse_class(data, refs=False):
    u2 = lambda o: (data[o] << 8) | data[o + 1]
    u4 = lambda o: struct.unpack_from('>I', data, o)[0]
    if data[:4] != b'\xca\xfe\xba\xbe':
        raise ValueError('not a class file')
    count = u2(8)
    tags = [0] * count
    vals = [None] * count
    off, i = 10, 1
    while i < count:
        tag = data[off]
        tags[i] = tag
        if tag == 1:                        # Utf8, decoded on use
            n = u2(off + 1)
            vals[i] = (off + 3, n)
            off += 3 + n
        elif tag in (3, 4):                 # Integer, Float
            vals[i] = off + 1
            off += 5
        elif tag in (5, 6):                 # Long, Double take two slots
            vals[i] = off + 1
            off += 9
            i += 1
        elif tag in (7, 8, 16, 19, 20):     # Class, String, MethodType, Module, Package
            vals[i] = u2(off + 1)
            off += 3
        elif tag in (9, 10, 11, 12, 17, 18):  # refs, NameAndType, Dynamic, InvokeDynamic
            vals[i] = (u2(off + 1), u2(off + 3))
            off += 5
        elif tag == 15:                     # MethodHandle
            vals[i] = (data[off + 1], u2(off + 2))
            off += 4
        else:
            raise ValueError('bad constant pool tag %d' % tag)
        i += 1

    strings = {}

    def utf(k):
        s = strings.get(k)
        if s is None:
            o, n = vals[k]
            s = strings[k] = data[o:o + n].decode('utf-8', 'replace')
        return s

    def cls(k):
        return utf(vals[k])

    def constant(k):
        t = tags[k]
        if t == 3:
            return struct.unpack_from('>i', data, vals[k])[0]
        if t == 4:
            return struct.unpack_from('>f', data, vals[k])[0]
        if t == 5:
            return struct.unpack_from('>q', data, vals[k])[0]
        if t == 6:
            return struct.unpack_from('>d', data, vals[k])[0]
        if t == 8:
            return utf(vals[k])
        return None

    ci = ClassInfo()
    ci.access = u2(off)
    ci.name = cls(u2(off + 2))
    sup = u2(off + 4)
    ci.super = cls(sup) if sup else None
    n = u2(off + 6)
    off += 8
    ci.interfaces = [cls(u2(off + 2 * k)) for k in range(n)]
    off += 2 * n
    for is_field in (True, False):
        n = u2(off)
        off += 2
        for _ in range(n):
            acc, name, desc, nattr = u2(off), utf(u2(off + 2)), utf(u2(off + 4)), u2(off + 6)
            off += 8
            const = None
            for _ in range(nattr):
                if is_field and utf(u2(off)) == 'ConstantValue':
                    const = constant(u2(off + 6))
                off += 6 + u4(off + 2)
            if is_field:
                ci.fields[(name, desc)] = (acc, const)
            else:
                ci.methods[(name, desc)] = acc
    if not refs:
        return ci

    bootstrap = []
    n = u2(off)
    off += 2
    for _ in range(n):
        if utf(u2(off)) == 'BootstrapMethods':
            p = off + 8
            for _ in range(u2(off + 6)):
                ref, nargs = u2(p), u2(p + 2)
                bootstrap.append((ref, [u2(p + 4 + 2 * a) for a in range(nargs)]))
                p += 4 + 2 * nargs
        off += 6 + u4(off + 2)

    for k in range(1, count):
        t = tags[k]
        if t == 7:
            name = cls(k)
            if name.startswith('['):
                name = name.lstrip('[')
                name = name[1:-1] if name.startswith('L') else ''
            if name.startswith(LWJGL):
                ci.class_refs.add(name)
        elif t in (9, 10, 11):
            owner = cls(vals[k][0])
            if owner.startswith(LWJGL):
                nat = vals[vals[k][1]]
                name, desc = utf(nat[0]), utf(nat[1])
                if t == 9:
                    ci.field_refs.add((owner, name, desc))
                else:
                    ci.method_refs.add((owner, name, desc, t == 11))
        elif t == 12:
            ci.desc_types.update(lwjgl_types(utf(vals[k][1])))
        elif t == 16:
            ci.desc_types.update(lwjgl_types(utf(vals[k])))
        elif t == 18:
            bsm, nat = vals[k]
            name, desc = utf(vals[nat][0]), utf(vals[nat][1])
            ret = desc[desc.index(')') + 1:]
            if ret.startswith('L' + LWJGL) and bsm < len(bootstrap):
                handle, args = bootstrap[bsm]
                owner = cls(vals[vals[handle][1]][0])
                if owner == 'java/lang/invoke/LambdaMetafactory' and args and tags[args[0]] == 16:
                    ci.lambdas.add((ret[1:-1], name, utf(vals[args[0]])))
    for (_, desc) in list(ci.fields) + list(ci.methods):
        ci.desc_types.update(lwjgl_types(desc))
    return ci


class Jars:
    """Classes of a classpath, parsed on first use; the first jar listing a class wins."""

    def __init__(self, paths):
        self.entries = {}
        self.parsed = {}
        for p in paths:
            z = zipfile.ZipFile(p)
            for n in z.namelist():
                if n.endswith('.class') and not n.startswith('META-INF/') and not n.endswith('module-info.class'):
                    self.entries.setdefault(n[:-6], (z, n))

    def get(self, name):
        if name not in self.parsed:
            e = self.entries.get(name)
            self.parsed[name] = parse_class(e[0].read(e[1])) if e else None
        return self.parsed[name]


def object_class():
    ci = ClassInfo()
    ci.name, ci.access = 'java/lang/Object', ACC_PUBLIC
    for name, desc in [('<init>', '()V'), ('equals', '(Ljava/lang/Object;)Z'), ('hashCode', '()I'),
                       ('toString', '()Ljava/lang/String;'), ('getClass', '()Ljava/lang/Class;'),
                       ('notify', '()V'), ('notifyAll', '()V'), ('wait', '()V'), ('wait', '(J)V'),
                       ('wait', '(JI)V')]:
        ci.methods[(name, desc)] = ACC_PUBLIC
    ci.methods[('clone', '()Ljava/lang/Object;')] = ACC_PROTECTED
    ci.methods[('finalize', '()V')] = ACC_PROTECTED
    return ci


class World:
    """Resolves references like the JVM: LWJGL classes come only from `lwjgl`."""

    def __init__(self, lwjgl, others=()):
        self.lwjgl = lwjgl
        self.others = list(others)
        self.obj = object_class()

    def get(self, name):
        if name.startswith(LWJGL):
            return self.lwjgl.get(name)
        for o in self.others:
            ci = o.get(name)
            if ci is not None:
                return ci
        return self.obj if name == 'java/lang/Object' else None

    def supertypes(self, name):
        """All superclasses and superinterfaces, and whether any of them is not indexed."""
        out, todo, seen, unknown = [], [name], set(), False
        while todo:
            c = todo.pop(0)
            if c in seen:
                continue
            seen.add(c)
            ci = self.get(c)
            if ci is None:
                unknown = True
                continue
            if c != name:
                out.append(ci)
            todo.extend(ci.interfaces)
            if ci.super:
                todo.append(ci.super)
        return out, unknown

    def find_method(self, owner, name, desc):
        """(declaring class, access) per JVMS 5.4.3.3/5.4.3.4, None if absent, UNKNOWN if undecidable."""
        unknown, c = False, owner
        while c:
            ci = self.get(c)
            if ci is None:
                unknown = True
                break
            acc = ci.methods.get((name, desc))
            if acc is not None:
                return c, acc
            c = ci.super
        supers, unk = self.supertypes(owner)
        for ci in supers:
            acc = ci.methods.get((name, desc))
            if ci.access & ACC_INTERFACE and acc is not None and not acc & (ACC_STATIC | ACC_PRIVATE):
                return ci.name, acc
        acc = self.obj.methods.get((name, desc))
        if acc is not None and acc & ACC_PUBLIC:
            return 'java/lang/Object', acc
        return UNKNOWN if unknown or unk else None

    def find_field(self, owner, name, desc):
        """(declaring class, access) per JVMS 5.4.3.2, None if absent, UNKNOWN if undecidable."""
        ci = self.get(owner)
        if ci is None:
            return UNKNOWN
        f = ci.fields.get((name, desc))
        if f is not None:
            return owner, f[0]
        unknown = False
        for s in ci.interfaces + ([ci.super] if ci.super else []):
            r = self.find_field(s, name, desc)
            if r is UNKNOWN:
                unknown = True
            elif r:
                return r
        return UNKNOWN if unknown else None

    def abstract_methods(self, name):
        """Methods left abstract in `name`'s hierarchy, as {(name, desc): declaring class}."""
        concrete, abstract = set(), {}
        ci = self.get(name)
        supers, unknown = self.supertypes(name)
        for c in [ci] + supers:
            for key, acc in c.methods.items():
                if acc & (ACC_STATIC | ACC_PRIVATE) or key[0] in ('<init>', '<clinit>'):
                    continue
                if acc & ACC_ABSTRACT:
                    abstract.setdefault(key, c.name)
                else:
                    concrete.add(key)
        return {k: v for k, v in abstract.items() if k not in concrete}, unknown


def access_str(acc, method):
    words = []
    for bit, word in [(ACC_PUBLIC, 'public'), (ACC_PROTECTED, 'protected'), (ACC_PRIVATE, 'private'),
                      (ACC_STATIC, 'static'), (ACC_FINAL, 'final'), (ACC_ABSTRACT, 'abstract')]:
        if acc & bit:
            words.append(word)
    if method and acc & ACC_NATIVE:
        words.append('native')
    return ' '.join(words) or 'package-private'


def class_kind(ci):
    if ci.access & ACC_INTERFACE:
        kind = 'interface'
    else:
        kind = ('abstract ' if ci.access & ACC_ABSTRACT else '') + ('final ' if ci.access & ACC_FINAL else '') + 'class'
    head = '%s %s %s' % ('public' if ci.access & ACC_PUBLIC else 'package-private', kind, ci.name)
    if ci.super and ci.super != 'java/lang/Object':
        head += ' extends ' + ci.super
    if ci.interfaces:
        head += (' extends ' if ci.access & ACC_INTERFACE else ' implements ') + ', '.join(ci.interfaces)
    return head


def fetch(url, cache, sha1=None):
    path = os.path.join(cache, hashlib.sha1(url.encode()).hexdigest()[:12] + '-' +
                        os.path.basename(urllib.parse.urlparse(url).path))
    if not os.path.exists(path):
        with urllib.request.urlopen(url, timeout=300) as r:
            data = r.read()
        if sha1 and hashlib.sha1(data).hexdigest() != sha1:
            sys.exit('SHA-1 mismatch for ' + url)
        with open(path + '.part', 'wb') as f:
            f.write(data)
        os.replace(path + '.part', path)
    return path


def minecraft_jars(version, cache):
    os.makedirs(cache, exist_ok=True)
    with open(fetch(MANIFEST, cache)) as f:
        manifest = json.load(f)
    entry = next((v for v in manifest['versions'] if v['id'] == version), None)
    if entry is None:
        sys.exit('Version %s is not in the manifest (latest: %s)' % (version, manifest['latest']))
    with open(fetch(entry['url'], cache, entry.get('sha1'))) as f:
        info = json.load(f)
    client = info['downloads']['client']
    user, ref, seen = [fetch(client['url'], cache, client['sha1'])], [], set()
    print('Minecraft %s (Java %s)' % (version, info.get('javaVersion', {}).get('majorVersion')))
    for lib in info['libraries']:
        art = lib.get('downloads', {}).get('artifact')
        parts = lib['name'].split(':')
        if not art or len(parts) != 3 or art['url'] in seen:
            continue   # native classifiers hold no classes of interest
        seen.add(art['url'])
        print('  library', lib['name'])
        (ref if parts[0] == 'org.lwjgl' else user).append(fetch(art['url'], cache, art.get('sha1')))
    return user, ref


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--version', help='Minecraft version to download and check, e.g. 26.1')
    ap.add_argument('--jar', action='append', default=[], help='jar to check instead of --version (repeatable)')
    ap.add_argument('--ref', action='append', default=[], help='LWJGL jars the checked jars were built against')
    ap.add_argument('--lwjgl', action='append', required=True, help='LWJGL jar(s) available at runtime')
    ap.add_argument('--jdk', action='append', default=[], help='JDK class jars (e.g. rt.jar) for supertypes outside LWJGL')
    ap.add_argument('--cache', default='mc-cache', help='download directory (default: %(default)s)')
    ap.add_argument('--dump', action='store_true', help='also list every member of missing classes from the reference jars')
    args = ap.parse_args()

    user_paths, ref_paths = list(args.jar), list(args.ref)
    if args.version:
        u, r = minecraft_jars(args.version, args.cache)
        user_paths += u
        ref_paths += r
    if not user_paths:
        ap.error('give --version or --jar')

    jdk = Jars(args.jdk)
    user = Jars(user_paths)
    world = World(Jars(args.lwjgl), [user, jdk])
    ref = World(Jars(ref_paths), [user, jdk]) if ref_paths else None

    # Parse every class of the checked jars, including multi-release variants, for references.
    classes = []
    for p in user_paths:
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if not n.endswith('.class') or n.endswith('module-info.class'):
                    continue
                data = z.read(n)
                versioned, has_refs = n.startswith('META-INF/'), b'org/lwjgl/' in data
                if versioned and not has_refs:
                    continue
                try:
                    ci = parse_class(data, refs=has_refs)
                except (ValueError, IndexError, struct.error) as e:
                    print('warning: cannot parse %s!%s: %s' % (os.path.basename(p), n, e))
                    continue
                classes.append(ci)
                if not versioned:
                    user.parsed.setdefault(ci.name, ci)
    print('Checked %d classes from %d jars against %s' % (len(classes), len(user_paths), ', '.join(args.lwjgl)))

    missing_classes, missing_methods, missing_fields, other, unchecked = {}, {}, {}, {}, {}

    def note(table, key, who):
        table.setdefault(key, set()).add(who)

    def ref_decl(kind, owner, name, desc):
        if not ref:
            return ''
        r = ref.find_method(owner, name, desc) if kind == 'method' else ref.find_field(owner, name, desc)
        if not r or r is UNKNOWN:
            return '  [not in reference jars]'
        decl, acc = r
        text = access_str(acc, kind == 'method')
        if kind == 'field':
            const = ref.get(decl).fields[(name, desc)][1]
            if const is not None:
                text += ' = %r' % (const,)
        return '  [reference: %s%s]' % (text, '' if decl == owner else ' in ' + decl)

    for ci in classes:
        who = ci.name
        for c in ci.class_refs | ci.desc_types:
            target = world.get(c)
            if target is None:
                note(missing_classes, c, who)
            elif not target.access & ACC_PUBLIC:
                note(other, 'IllegalAccessError: %s is not public' % c, who)
        for owner, name, desc, iface in ci.method_refs:
            target = world.get(owner)
            if target is None:
                note(missing_classes, owner, who)
                continue
            if bool(target.access & ACC_INTERFACE) != iface:
                note(other, 'IncompatibleClassChangeError: %s is %san interface, called as %s method %s%s' % (
                    owner, '' if target.access & ACC_INTERFACE else 'not ', 'interface' if iface else 'class', name, desc), who)
            r = world.find_method(owner, name, desc)
            if r is None:
                note(missing_methods, (owner, name, desc), who)
            elif r is UNKNOWN:
                note(unchecked, 'method %s.%s%s' % (owner, name, desc), who)
            elif ref:
                rr = ref.find_method(owner, name, desc)
                if rr and rr is not UNKNOWN:
                    if (rr[1] ^ r[1]) & ACC_STATIC:
                        note(other, 'IncompatibleClassChangeError: %s.%s%s is %s here but %s in the reference' % (
                            owner, name, desc, access_str(r[1], True), access_str(rr[1], True)), who)
                    if rr[1] & ACC_PUBLIC and not r[1] & ACC_PUBLIC:
                        note(other, 'IllegalAccessError: %s.%s%s is %s here but public in the reference' % (
                            owner, name, desc, access_str(r[1], True)), who)
        for owner, name, desc in ci.field_refs:
            if world.get(owner) is None:
                note(missing_classes, owner, who)
                continue
            r = world.find_field(owner, name, desc)
            if r is None:
                note(missing_fields, (owner, name, desc), who)
            elif r is UNKNOWN:
                note(unchecked, 'field %s.%s:%s' % (owner, name, desc), who)
            elif ref:
                rr = ref.find_field(owner, name, desc)
                if rr and rr is not UNKNOWN and (rr[1] ^ r[1]) & ACC_STATIC:
                    note(other, 'IncompatibleClassChangeError: field %s.%s is %s here but %s in the reference' % (
                        owner, name, access_str(r[1], False), access_str(rr[1], False)), who)
        for iface, name, desc in ci.lambdas:
            target = world.get(iface)
            if target is None:
                note(missing_classes, iface, who)
                continue
            if not target.access & ACC_INTERFACE:
                note(other, 'lambda target %s is not an interface' % iface, who)
                continue
            abstract, unknown = world.abstract_methods(iface)
            abstract = {k: v for k, v in abstract.items() if k not in world.obj.methods}
            if (name, desc) not in abstract:
                note(other, 'AbstractMethodError: lambda implements %s.%s%s, which %s does not declare' % (
                    iface, name, desc, iface), who)
            for (n2, d2), decl in abstract.items():
                if (n2, d2) != (name, desc):
                    note(other, 'AbstractMethodError: lambda for %s leaves %s.%s%s abstract' % (iface, decl, n2, d2), who)

    # Concrete classes extending or implementing LWJGL types must implement what LWJGL leaves abstract.
    for ci in classes:
        if ci.access & (ACC_INTERFACE | ACC_ABSTRACT) or ci.name.startswith(LWJGL):
            continue
        supers, unknown = world.supertypes(ci.name)
        lw = [s for s in supers if s.name.startswith(LWJGL)]
        if not lw:
            continue
        abstract, _ = world.abstract_methods(ci.name)
        for (n2, d2), decl in abstract.items():
            if decl.startswith(LWJGL):
                note(other, 'AbstractMethodError: %s does not implement %s.%s%s' % (ci.name, decl, n2, d2), ci.name)
        for (n2, d2), acc in ci.methods.items():
            for s in lw:
                sacc = s.methods.get((n2, d2))
                if sacc is not None and sacc & ACC_FINAL and not acc & (ACC_STATIC | ACC_PRIVATE):
                    note(other, 'IncompatibleClassChangeError: %s overrides final %s.%s%s' % (ci.name, s.name, n2, d2), ci.name)

    def users(s):
        s = sorted(s)
        return ', '.join(s[:3]) + (' and %d more' % (len(s) - 3) if len(s) > 3 else '')

    total = len(missing_classes) + len(missing_methods) + len(missing_fields) + len(other)
    print()
    print('=== Missing classes (NoClassDefFoundError): %d' % len(missing_classes))
    for c in sorted(missing_classes):
        rc = ref.get(c) if ref else None
        print('%s%s' % (c, '  [reference: %s]' % class_kind(rc) if rc else ''))
        print('    used by: ' + users(missing_classes[c]))
        if args.dump and rc:
            for (n, d), (acc, const) in sorted(rc.fields.items()):
                print('    | field %s %s:%s%s' % (access_str(acc, False), n, d, '' if const is None else ' = %r' % (const,)))
            for (n, d), acc in sorted(rc.methods.items()):
                print('    | method %s %s%s' % (access_str(acc, True), n, d))
        members =sorted({(n, d) for ci in classes for (o, n, d, _) in ci.method_refs if o == c})
        for n, d in members:
            print('    method %s%s%s' % (n, d, ref_decl('method', c, n, d)))
        fields = sorted({(n, d) for ci in classes for (o, n, d) in ci.field_refs if o == c})
        for n, d in fields:
            print('    field %s:%s%s' % (n, d, ref_decl('field', c, n, d)))
    print()
    print('=== Missing methods (NoSuchMethodError): %d' % len(missing_methods))
    for (o, n, d) in sorted(missing_methods):
        print('%s.%s%s%s' % (o, n, d, ref_decl('method', o, n, d)))
        print('    used by: ' + users(missing_methods[(o, n, d)]))
    print()
    print('=== Missing fields (NoSuchFieldError): %d' % len(missing_fields))
    for (o, n, d) in sorted(missing_fields):
        print('%s.%s:%s%s' % (o, n, d, ref_decl('field', o, n, d)))
        print('    used by: ' + users(missing_fields[(o, n, d)]))
    print()
    print('=== Other linkage problems: %d' % len(other))
    for k in sorted(other):
        print(k)
        print('    used by: ' + users(other[k]))
    if unchecked:
        print()
        print('=== Not checked (supertype outside LWJGL not indexed, pass --jdk): %d' % len(unchecked))
        for k in sorted(unchecked):
            print(k + '    used by: ' + users(unchecked[k]))
    print()
    print('RESULT: %d problem(s)' % total)


if __name__ == '__main__':
    main()
