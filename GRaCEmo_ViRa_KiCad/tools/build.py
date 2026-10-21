import os, json, shutil, csv, sys
sys.path.insert(0, os.path.dirname(__file__))
from kgen import *
import design
from design import ALL, ROOT_UUID, root

OUT = "/home/claude/out/GRaCEmo_ViRa_KiCad"
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT + "/libs")
os.makedirs(OUT + "/docs")

root.text(["GRaCEmo ViRa - hardware overview (DRAFT 0.1)",
           "Humanoid mobile robot: 4-wheel base, articulated upper body, AI perception, voice, autonomous navigation.",
           "Voltage domains: VBATT 24V class (21-29.4V) | VMOT via K1 | V5_LOGIC/V5_SENS | V_COMPUTE_IN | V_LIDAR/V_AUDIO TBD | 3V3_LOGIC",
           "Cross-sheet connectivity uses GLOBAL labels (nets are identical across sheets); sheet symbols below are navigation blocks.",
           "VALIDATION STATUS: files parsed by an independent parser + custom pre-check. NOT opened in KiCad. KiCad ERC NOT run."], 1.5)

all_parts, all_conns, papers = [], [], {}
for sh in ALL:
    txt, parts, conns, paper = render_sheet(sh, ROOT_UUID, None)
    if sh.idx == 0:
        blocks = []
        for i, s in enumerate(ALL[1:]):
            col, row = divmod(i, 6)
            x, y = 20 + col * 130, 135 + row * 22
            blocks.append(
                f'(sheet (at {x} {y}) (size 110 14) (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0)) (uuid "{s.uuid}")\n'
                f'    (property "Sheetname" "{s.title}" (at {x} {y - 1} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))\n'
                f'    (property "Sheetfile" "{s.fname}" (at {x} {y + 15} 0) (effects (font (size 1.27 1.27)) (justify left top)))\n'
                f'    (instances (project "{PROJECT}" (path "/{ROOT_UUID}" (page "{s.idx + 1}")))))')
        txt = txt.replace("\n  (sheet_instances", "\n  " + "\n  ".join(blocks) + "\n  (sheet_instances", 1)
    open(f"{OUT}/{sh.fname}", "w").write(txt)
    all_parts += parts
    all_conns += [(sh.name,) + c for c in conns]
    papers[sh.name] = paper

write_symlib(f"{OUT}/libs/GRaCEmo.kicad_sym")
open(f"{OUT}/sym-lib-table", "w").write(
    '(sym_lib_table\n  (version 7)\n  (lib (name "GRaCEmo")(type "KiCad")(uri "${KIPRJMOD}/libs/GRaCEmo.kicad_sym")(options "")(descr "GRaCEmo ViRa project symbols"))\n)\n')
open(f"{OUT}/fp-lib-table", "w").write('(fp_lib_table\n  (version 7)\n)\n')
pro = {"meta": {"filename": PROJECT + ".kicad_pro", "version": 1}, "schematic": {"drawing": {"default_text_size": 1.27}},
       "sheets": [[ROOT_UUID, "Root"]] + [[s.uuid, s.title] for s in ALL[1:]], "libraries": {"pinned_symbol_libs": []}}
json.dump(pro, open(f"{OUT}/{PROJECT}.kicad_pro", "w"), indent=2)

json.dump(dict(parts=[{k: v for k, v in p.items()} for p in all_parts], conns=all_conns, papers=papers),
          open("/home/claude/out/model.json", "w"), indent=1, default=str)
print("sheets:", {k: v for k, v in papers.items()})
print("parts:", len(all_parts), "conns:", len(all_conns))
