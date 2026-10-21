"""Minimal KiCad 7-format (.kicad_sch v20230121) generator: symbol library, auto-layout, labels."""
import math, uuid

NS = uuid.UUID("6f1d9a52-3c1e-4b7a-9d55-0a6c1e7b2f10")
PROJECT = "GRaCEmo_ViRa_Hardware_Overview"
_uc = [0]


def U(tag=""):
    _uc[0] += 1
    return str(uuid.uuid5(NS, f"{tag}-{_uc[0]}"))


def esc(s):
    return str(s).replace("\\", "\\\\").replace('"', "'").replace("\n", "\\n")


def f(x):
    return ("%.4f" % x).rstrip("0").rstrip(".") if x != int(x) else str(int(x))


def snap(v, g=2.54):
    return round(round(v / g) * g, 4)


# ------------------------------------------------------------------ symbols
class SymDef:
    def __init__(self, key, ref, desc, kind, left, right, hide_names=False, power=False, in_bom=True):
        self.key, self.ref, self.desc, self.kind = key, ref, desc, kind
        self.left, self.right = left, right  # lists of (name, type)
        self.hide_names, self.power, self.in_bom = hide_names, power, in_bom
        self.pins = {}  # name -> dict(num,x,y,side,type,len)
        self._build()

    def _build(self):
        k = self.kind
        n = max(len(self.left), len(self.right), 1)
        self.gfx = []
        if k in ("res", "fuse", "sw", "diode", "cap", "cp", "nt", "tp", "pwrflag"):
            hb = {"res": 2.54, "fuse": 2.54, "sw": 2.54, "diode": 3.81, "cap": 1.27, "cp": 1.27,
                  "nt": 1.27, "tp": 0, "pwrflag": 0}[k]
            self.w = 2 * hb
            self.top = 2.54
            self.h = 5.08
            if k == "res":
                self.gfx.append(("rect", -2.54, 1.016, 2.54, -1.016, "none"))
                inner = 2.54
            elif k == "fuse":
                self.gfx += [("rect", -2.54, 1.016, 2.54, -1.016, "none"), ("poly", [(-2.54, 0), (2.54, 0)])]
                inner = 2.54
            elif k == "sw":
                self.gfx += [("poly", [(-2.54, 0), (-1.27, 0)]), ("poly", [(-1.27, 0), (1.27, 1.524)]),
                             ("poly", [(1.27, 0), (2.54, 0)]), ("circle", -1.27, 0, 0.3), ("circle", 1.27, 0, 0.3)]
                inner = 2.54
            elif k == "diode":
                self.gfx += [("poly", [(1.27, 1.27), (1.27, -1.27), (-1.27, 0), (1.27, 1.27)]),
                             ("poly", [(-1.27, 1.27), (-1.27, -1.27)])]
                inner = 1.27
                hb = 3.81
            elif k in ("cap", "cp"):
                self.gfx += [("poly", [(-0.635, 2.032), (-0.635, -2.032)]), ("poly", [(0.635, 2.032), (0.635, -2.032)])]
                inner = 0.635
                hb = 3.81
            elif k == "nt":
                self.gfx += [("poly", [(-1.27, 0), (1.27, 0)])]
                inner = 1.27
                hb = 3.81
            elif k == "tp":
                self.gfx += [("circle", 0, 0, 0.762)]
                inner = 0.762
                hb = 2.54
            else:  # pwrflag
                self.gfx += [("poly", [(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54), (1.016, 1.905), (0, 1.27)])]
                inner = 0
            # pins: left pin1 at -hb, right pin at +hb
            if k == "pwrflag":
                nm, ty = self.right[0] if self.right else self.left[0]
                self.pins[nm] = dict(num="1", x=0, y=0, side="left", type=ty, len=0, ang=90)
            else:
                if self.left:
                    nm, ty = self.left[0]
                    self.pins[nm] = dict(num="1", x=-hb, y=0, side="left", type=ty, len=hb - inner, ang=0)
                if self.right:
                    nm, ty = self.right[0]
                    self.pins[nm] = dict(num="2", x=hb, y=0, side="right", type=ty, len=hb - inner, ang=180)
            self.hb = hb
            return
        # box
        maxl = max([len(a) for a, _ in self.left] + [0])
        maxr = max([len(a) for a, _ in self.right] + [0])
        gap = 6 if (self.left and self.right) else 4
        w = max(15.24, (maxl + maxr) * 1.12 + gap)
        w = math.ceil(w / 5.08) * 5.08
        self.w = w
        self.h = (n + 1) * 2.54
        self.top = self.h / 2
        self.hb = w / 2 + 2.54
        num = 1
        for side, lst in (("left", self.left), ("right", self.right)):
            for i, (nm, ty) in enumerate(lst):
                y = round(self.top - 2.54 * (i + 1), 4)
                x = -(w / 2 + 2.54) if side == "left" else (w / 2 + 2.54)
                self.pins[nm] = dict(num=str(num), x=x, y=y, side=side, type=ty, len=2.54,
                                     ang=0 if side == "left" else 180)
                num += 1
        self.gfx.append(("rect", -w / 2, self.top, w / 2, -self.top, "background"))

    # ---- s-expr text for lib_symbols / .kicad_sym
    def sexpr(self, prefix="GRaCEmo:", indent="  "):
        nm = self.key
        out = []
        a = out.append
        pn = "(pin_names (offset 0) hide)" if self.hide_names or self.kind in ("res", "fuse", "sw", "diode", "cap", "cp", "nt", "tp", "pwrflag") else "(pin_names (offset 1.016))"
        pnum = "(pin_numbers hide)" if self.kind in ("tp", "pwrflag") else ""
        a(f'(symbol "{prefix}{nm}" {"(power) " if self.power else ""}{pnum} {pn} (in_bom {"yes" if self.in_bom else "no"}) (on_board {"yes" if self.in_bom else "no"})')
        ty = self.top + 2.54
        a(f'  (property "Reference" "{self.ref}" (at 0 {f(ty)} 0) (effects (font (size 1.27 1.27))))')
        a(f'  (property "Value" "{esc(nm)}" (at 0 {f(-ty)} 0) (effects (font (size 1.27 1.27))))')
        a('  (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
        a('  (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
        a(f'  (property "ki_description" "{esc(self.desc)}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))')
        a(f'  (symbol "{nm}_0_1"')
        for g in self.gfx:
            if g[0] == "rect":
                a(f'    (rectangle (start {f(g[1])} {f(g[2])}) (end {f(g[3])} {f(g[4])}) (stroke (width 0.254) (type default)) (fill (type {g[5]})))')
            elif g[0] == "poly":
                pts = " ".join(f"(xy {f(x)} {f(y)})" for x, y in g[1])
                a(f'    (polyline (pts {pts}) (stroke (width 0.254) (type default)) (fill (type none)))')
            elif g[0] == "circle":
                a(f'    (circle (center {f(g[1])} {f(g[2])}) (radius {f(g[3])}) (stroke (width 0.254) (type default)) (fill (type none)))')
        a("  )")
        a(f'  (symbol "{nm}_1_1"')
        for pname, p in self.pins.items():
            shown = '' if self.kind in ("tp", "pwrflag") else ''
            a(f'    (pin {p["type"]} line (at {f(p["x"])} {f(p["y"])} {p["ang"]}) (length {f(p["len"])}) (name "{esc(pname)}" (effects (font (size 1.016 1.016)))) (number "{p["num"]}" (effects (font (size 1.016 1.016)))))')
        a("  )")
        a(")")
        return "\n".join(indent + l for l in out)


SYM = {}


def sd(key, ref, desc, kind, left=(), right=(), **kw):
    SYM[key] = SymDef(key, ref, desc, kind, list(left), list(right), **kw)
    return SYM[key]


# ------------------------------------------------------------------ sheet / layout
class Item:
    pass


class Sheet:
    def __init__(self, idx, name, title, comments=()):
        self.idx, self.name, self.title, self.comments = idx, name, title, list(comments)
        self.fname = f"{name}.kicad_sch"
        self.uuid = U("sheet")
        self.items = []   # ('part'|'text', ...)
        self.placed = []  # parts placed after layout
        self.used = {}

    def part(self, sym, value, nets, **meta):
        self.items.append(("part", sym, value, nets, meta))

    def text(self, lines, size=1.27, bold=False):
        if isinstance(lines, str):
            lines = lines.split("\n")
        self.items.append(("text", lines, size, bold))


REFCNT = {}


def next_ref(prefix):
    REFCNT[prefix] = REFCNT.get(prefix, 0) + 1
    return f"{prefix}{REFCNT[prefix]}"


PAPERS = {"A3": (420, 297), "A2": (594, 420), "A1": (841, 594)}
STUB = 5.08


def lblw(s):
    return len(s) * 1.45 + 4.5


def measure(it):
    if it[0] == "text":
        _, lines, size, bold = it
        w = max(len(l) for l in lines) * 1.05 * size / 1.27 + 4
        h = len(lines) * size * 1.6 + 4
        return w, h
    _, sym, value, nets, meta = it
    s = SYM[sym]
    lw = rw = 0
    for pname, p in s.pins.items():
        net = nets.get(pname)
        if net is None:
            raise KeyError(f"{sym}: pin '{pname}' has no net/NC entry")
        wid = 0 if net == "NC" else lblw(net)
        if p["side"] == "left":
            lw = max(lw, wid)
        else:
            rw = max(rw, wid)
    left_ext = (s.hb if s.left or s.kind == "pwrflag" else s.w / 2) + (STUB + lw if lw else 2) + 1
    right_ext = (s.hb if s.right else s.w / 2) + (STUB + rw if rw else 2) + 1
    textw = max(len(value), 6) * 1.2 + 2
    total = left_ext + right_ext
    if textw > total:
        extra = (textw - total) / 2
        left_ext += extra
        right_ext += extra
    h = s.h + 14
    return left_ext, right_ext, h


def layout(sheet, paper, top_y):
    pw, ph = PAPERS[paper]
    mx, my = 15.24, 15.24
    x = mx
    y = top_y
    rowh = 0
    placed = []
    maxw = pw - 2 * mx
    for it in sheet.items:
        if it[0] == "text":
            w, h = measure(it)
            if x + w > mx + maxw and x > mx:
                x = mx
                y += rowh + 6
                rowh = 0
            placed.append((it, x, y, w, h))
            x += w + 4
            rowh = max(rowh, h)
        else:
            le, re, h = measure(it)
            w = le + re + 6
            if x + w > mx + maxw and x > mx:
                x = mx
                y += rowh + 4
                rowh = 0
            ax = snap(x + le)
            ay = snap(y + h / 2)
            placed.append((it, ax, ay, w, h))
            x += w
            rowh = max(rowh, h)
    end_y = y + rowh
    return placed, end_y, pw, ph


def render_sheet(sheet, root_uuid, ref_map):
    """returns (kicad_sch text, parts list for BOM, list of (ref,pin,net,type))"""
    top_y = 38 + 4 * max(0, len(sheet.comments))
    chosen = None
    for paper in ("A3", "A2", "A1"):
        placed, end_y, pw, ph = layout(sheet, paper, top_y)
        if end_y < ph - 28:
            chosen = (paper, placed, pw, ph)
            break
    if chosen is None:
        raise RuntimeError(f"sheet {sheet.name} does not fit on A1 (end_y={end_y})")
    paper, placed, pw, ph = chosen
    body, wires, labels, texts, ncs = [], [], [], [], []
    used_syms = {}
    parts = []
    conns = []
    inst_path = f'/{root_uuid}/{sheet.uuid}' if sheet.idx > 0 else f'/{root_uuid}'
    for it, ax, ay, w, h in placed:
        if it[0] == "text":
            _, lines, size, bold = it
            txt = "\\n".join(esc(l) for l in lines)
            texts.append(f'(text "{txt}" (at {f(ax)} {f(ay)} 0) (effects (font (size {f(size)} {f(size)}){" bold" if bold else ""}) (justify left top)) (uuid "{U("t")}"))')
            continue
        _, sym, value, nets, meta = it
        s = SYM[sym]
        used_syms[sym] = s
        if meta.get("ref"):
            ref = meta["ref"]
        else:
            ref = next_ref(s.ref)
        sid = U("sym")
        fp = meta.get("fp", "")
        ds = meta.get("ds", "")
        pinlines = []
        for pname, p in s.pins.items():
            pinlines.append(f'(pin "{p["num"]}" (uuid "{U("pin")}"))')
            net = nets[pname]
            px, py = ax + p["x"], ay - p["y"]
            if net == "NC":
                ncs.append(f'(no_connect (at {f(px)} {f(py)}) (uuid "{U("nc")}"))')
                conns.append((ref, pname, p["num"], "NC", p["type"], sym))
                continue
            conns.append((ref, pname, p["num"], net, p["type"], sym))
            if p["side"] == "left":
                ex = px - STUB
                wires.append(f'(wire (pts (xy {f(px)} {f(py)}) (xy {f(ex)} {f(py)})) (stroke (width 0) (type default)) (uuid "{U("w")}"))')
                labels.append(f'(global_label "{net}" (shape bidirectional) (at {f(ex)} {f(py)} 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{U("l")}") (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {f(ex)} {f(py)} 0) (effects (font (size 1.27 1.27)) (justify left) hide)))')
            else:
                ex = px + STUB
                wires.append(f'(wire (pts (xy {f(px)} {f(py)}) (xy {f(ex)} {f(py)})) (stroke (width 0) (type default)) (uuid "{U("w")}"))')
                labels.append(f'(global_label "{net}" (shape bidirectional) (at {f(ex)} {f(py)} 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{U("l")}") (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {f(ex)} {f(py)} 0) (effects (font (size 1.27 1.27)) (justify left) hide)))')
        ty = s.top + 2.54
        flag = s.kind == "pwrflag"
        props = [
            f'(property "Reference" "{ref}" (at {f(ax)} {f(ay - ty)} 0) (effects (font (size 1.27 1.27))))',
            f'(property "Value" "{esc(value)}" (at {f(ax)} {f(ay + ty)} 0) (effects (font (size 1.27 1.27))))',
            f'(property "Footprint" "{esc(fp)}" (at {f(ax)} {f(ay)} 0) (effects (font (size 1.27 1.27)) hide))',
            f'(property "Datasheet" "{esc(ds)}" (at {f(ax)} {f(ay)} 0) (effects (font (size 1.27 1.27)) hide))',
        ]
        for key in ("Manufacturer", "MPN", "Function", "Voltage", "Current", "Status", "Sim_Class", "Notes"):
            v = meta.get(key.lower(), "")
            if v:
                props.append(f'(property "{key}" "{esc(v)}" (at {f(ax)} {f(ay)} 0) (effects (font (size 1.27 1.27)) hide))')
        bom = "yes" if s.in_bom else "no"
        body.append(
            f'(symbol (lib_id "GRaCEmo:{sym}") (at {f(ax)} {f(ay)} 0) (unit 1) (in_bom {bom}) (on_board {bom}) (dnp no) (uuid "{sid}")\n    '
            + "\n    ".join(props) + "\n    " + " ".join(pinlines)
            + f'\n    (instances (project "{PROJECT}" (path "{inst_path}" (reference "{ref}") (unit 1)))))')
        parts.append(dict(ref=ref, sym=sym, value=value, sheet=sheet.name, meta=meta, in_bom=s.in_bom,
                          fp=fp, ds=ds))
    libtxt = "\n".join(s.sexpr() for s in used_syms.values())
    tb = (f'(title_block (title "{esc(sheet.title)}") (date "2026-10-19") (rev "0.1-DRAFT") '
          f'(company "GRaCEmo ViRa") ' + " ".join(f'(comment {i+1} "{esc(c)}")' for i, c in enumerate(sheet.comments[:9])) + ")")
    head = f'''(kicad_sch (version 20230121) (generator eeschema)

  (uuid "{root_uuid if sheet.idx == 0 else sheet.uuid}")

  (paper "{paper}")

  {tb}

  (lib_symbols
{libtxt}
  )
'''
    htitle = f'(text "{esc(sheet.title)}" (at 15.24 22 0) (effects (font (size 3.5 3.5) bold) (justify left bottom)) (uuid "{U("t")}"))'
    parts_txt = "\n  ".join(texts + body + wires + labels + ncs)
    tail = '\n  (sheet_instances (path "/" (page "%d")))\n)\n' % (sheet.idx + 1)
    return head + "  " + htitle + "\n  " + parts_txt + tail, parts, conns, paper


def write_symlib(path):
    txt = '(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n'
    txt += "\n".join(s.sexpr(prefix="") for s in SYM.values())
    txt += "\n)\n"
    open(path, "w").write(txt)
