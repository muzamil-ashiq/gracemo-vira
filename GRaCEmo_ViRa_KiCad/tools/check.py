"""Independent pre-check (NOT KiCad ERC): parse files with kiutils, rebuild nets from geometry, apply basic ERC-like rules."""
import sys, os, glob, collections
from kiutils.schematic import Schematic

D = sys.argv[1]
files = sorted(glob.glob(D + "/*.kicad_sch"))
report, errs, warns = [], [], []
nets = collections.defaultdict(list)       # net -> [(sheet, ref, pin, type)]
pin_nc = []
lab_names = collections.defaultdict(set)
refs = collections.Counter()
for fp in files:
    sch = Schematic.from_file(fp)
    sheet = os.path.basename(fp)[:-10]
    libs = {s.libId.split(":")[-1] if ":" in s.libId else s.libId: s for s in sch.libSymbols}
    libs.update({s.entryName: s for s in sch.libSymbols})
    # union-find over points
    par = {}
    def find(a):
        par.setdefault(a, a)
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    def union(a, b):
        par[find(a)] = find(b)
    key = lambda x, y: (round(x, 3), round(y, 3))
    for w in sch.graphicalItems:
        if w.type == "wire":
            a, b = key(w.points[0].X, w.points[0].Y), key(w.points[1].X, w.points[1].Y)
            union(a, b)
    ptname = {}
    for l in sch.globalLabels:
        k = key(l.position.X, l.position.Y)
        find(k)
        ptname.setdefault(k, set()).add(l.text)
    ncpts = {key(n.position.X, n.position.Y) for n in sch.noConnects}
    pinpts = []
    for s in sch.schematicSymbols:
        ref = [p.value for p in s.properties if p.key == "Reference"][0]
        refs[ref] += 1
        lid = s.libId.split(":")[-1]
        ls = libs.get(lid)
        if ls is None:
            errs.append(f"{sheet}: {ref} lib symbol {s.libId} missing")
            continue
        for u in ls.units:
            for p in u.pins:
                x, y = s.position.X + p.position.X, s.position.Y - p.position.Y
                pinpts.append((key(x, y), ref, p.name, p.electricalType, lid))
    # net per component of union-find
    compname = collections.defaultdict(set)
    for k, names in ptname.items():
        compname[find(k)] |= names
    for c, names in compname.items():
        if len(names) > 1:
            errs.append(f"{sheet}: wire joins different labels {names}")
    for k, ref, pn, et, lid in pinpts:
        if k in ncpts:
            pin_nc.append((sheet, ref, pn))
            continue
        r = find(k)
        nm = compname.get(r)
        if not nm:
            if et == "no_connect":
                continue
            errs.append(f"{sheet}: {ref} pin {pn} unconnected (no label, no NC marker)")
            continue
        nets[list(nm)[0]].append((sheet, ref, pn, et))
    # label with no pin
    pinkeys = {p[0] for p in pinpts}
    for l in sch.globalLabels:
        k = key(l.position.X, l.position.Y)
        r = find(k)
        if not any(find(pk) == r for pk in pinkeys):
            errs.append(f"{sheet}: dangling label {l.text}")
for r, c in refs.items():
    if c > 1:
        errs.append(f"duplicate reference {r} x{c}")
for n, members in sorted(nets.items()):
    types = [m[3] for m in members]
    real = [m for m in members if m[3] != "no_connect"]
    if len(real) < 2:
        warns.append(f"net {n}: only {len(real)} pin ({[m[1]+'.'+m[2] for m in real]})")
    po = types.count("power_out")
    pi = types.count("power_in")
    flags = [m for m in members if m[1].startswith("#FLG")]
    if po > 1 and not (len(flags) == po - 1 and False):
        # PWR_FLAG + another power_out is fine in KiCad
        if po - len(flags) > 1:
            errs.append(f"net {n}: multiple power_out drivers {[m[1]+'.'+m[2] for m in members if m[3]=='power_out']}")
    if pi and po == 0:
        errs.append(f"net {n}: power_in pins without power_out/PWR_FLAG {[m[1]+'.'+m[2] for m in members if m[3]=='power_in']}")
    outs = [m for m in members if m[3] == "output"]
    if len(outs) > 1:
        errs.append(f"net {n}: multiple output drivers {[m[1]+'.'+m[2] for m in outs]}")
    ins = types.count("input")
    if ins and not (outs or po or "bidirectional" in types or "passive" in types):
        errs.append(f"net {n}: inputs with no driver")
print("files:", len(files), "nets:", len(nets), "NC pins:", len(pin_nc))
print("ERRORS:", len(errs))
for e in errs:
    print("  E", e)
print("WARNINGS:", len(warns))
for w in warns:
    print("  W", w)
import json
json.dump(dict(errors=errs, warnings=warns, nets=len(nets), files=len(files), nc=len(pin_nc)), open("/home/claude/out/precheck.json", "w"))
