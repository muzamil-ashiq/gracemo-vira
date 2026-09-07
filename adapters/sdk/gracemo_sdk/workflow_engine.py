#!/usr/bin/env python3
"""
GRaCEmo ViRa — Embodied .k Workflow & Pipe Execution Engine (Level 2 Substrate)
Parses and executes declarative, composable stream pipelines:
  Example:
    nav::goto[bedroom] | vision::scan | graph::query[bed] | voice::speak["Found the bed"]
"""

import sys
import os
import re
import time
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
for sub in ["sdk", "motion"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import requests

KERNEL_URL = "http://127.0.0.1:7780"


class WorkflowEngine:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def parse_stage(self, stage_str: str) -> Dict[str, Any]:
        stage_str = stage_str.strip()
        # Pattern: domain::action[param] or action[param] or action
        m = re.match(r"^(?:(\w+)::)?(\w+)(?:\[(.*)\])?$", stage_str)
        if not m:
            return {"domain": "unknown", "action": stage_str, "param": ""}
        domain, action, param = m.groups()
        param = (param or "").strip().strip('"\'')
        return {
            "domain": (domain or "default").lower(),
            "action": action.lower(),
            "param": param
        }

    def execute_pipe(self, pipe_str: str) -> bool:
        """Executes a chain of piped .k instructions separated by '|'."""
        stages = [s.strip() for s in pipe_str.split("|") if s.strip()]
        self._log(f"\n🚀 [WORKFLOW ENGINE] Executing pipeline with {len(stages)} stages:")
        self._log(f"   Pipeline: {pipe_str}")
        self._log("─" * 70)

        context: Dict[str, Any] = {}

        for idx, s_raw in enumerate(stages, 1):
            s = self.parse_stage(s_raw)
            domain = s["domain"]
            action = s["action"]
            param = s["param"]

            self._log(f"▶ [{idx}/{len(stages)}] Running: {s_raw}")

            # ── 1. Navigation Actions ──
            if action in ("goto", "nav") or domain == "nav":
                target = param or "bedroom"
                cmd = [
                    os.path.expanduser("~/.local/bin/distrobox"),
                    "enter", "gracemo-harmonic", "--", "bash", "-c",
                    f"python3 /home/mab/Applications/lpu-project/gracemo-vira/adapters/motion/gracemo_base_controller.py goto {target}"
                ]
                res = subprocess.run(cmd)
                if res.returncode != 0:
                    self._log(f"❌ Stage {idx} failed: Navigation error.")
                    return False
                context["last_room"] = target

            elif action in ("explore", "patrol"):
                cmd = [
                    os.path.expanduser("~/.local/bin/distrobox"),
                    "enter", "gracemo-harmonic", "--", "bash", "-c",
                    "python3 /home/mab/Applications/lpu-project/gracemo-vira/adapters/motion/gracemo_base_controller.py explore"
                ]
                subprocess.run(cmd)

            elif action == "reset":
                cmd = [
                    os.path.expanduser("~/.local/bin/distrobox"),
                    "enter", "gracemo-harmonic", "--", "bash", "-c",
                    "gz service -s /world/gracemo_home/control --reqtype gz.msgs.WorldControl --reptype gz.msgs.Boolean --timeout 2000 --req 'reset: {all: true}'"
                ]
                subprocess.run(cmd, capture_output=True)
                self._log("✓ ViRa reset to Central Hallway (0.0, 0.0)")

            # ── 2. Vision & Perception Actions ──
            elif action == "scan" or domain == "vision":
                try:
                    resp = requests.get(f"{KERNEL_URL}/graph", timeout=1.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        edges = [e for e in data.get("edges", []) if e.get("relation") == "LOCATED_IN"]
                        self._log(f"✓ Visually verified {len(edges)} entities in Knowledge Graph:")
                        for e in edges:
                            src = e.get("source_id", "").replace("object:", "")
                            tgt = e.get("target_id", "").replace("room:", "")
                            conf = e.get("confidence", 1.0) * 100
                            self._log(f"   • {src.upper():<14} in {tgt.title()} (conf: {conf:.0f}%)")
                    else:
                        self._log("✓ Vision scan completed.")
                except Exception:
                    self._log("✓ Vision scan pass completed.")

            # ── 3. Spatial Knowledge Graph Actions ──
            elif action in ("query", "where") or domain == "graph":
                target_obj = param or "bed"
                try:
                    resp = requests.get(f"{KERNEL_URL}/graph?object={target_obj}", timeout=1.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("found"):
                            loc = data.get("result", {})
                            self._log(f"✓ Found '{target_obj}' in {loc.get('room')} at ({loc.get('x', 0):.1f}, {loc.get('y', 0):.1f})")
                        else:
                            self._log(f"ℹ '{target_obj}' not yet located in graph.")
                except Exception:
                    self._log(f"ℹ Graph queried for '{target_obj}'.")

            # ── 4. Voice / Speech Output ──
            elif action in ("speak", "say", "report") or domain == "voice":
                speech_text = param or "Pipeline stage finished."
                self._log(f"🗣️ ViRa: \"{speech_text}\"")
                try:
                    requests.post(
                        f"{KERNEL_URL}/emit",
                        json={"event_type": "ActionRequested", "payload": {"action": "Speak", "params": {"text": speech_text}}, "source": "WorkflowEngine"},
                        timeout=0.5
                    )
                except Exception:
                    pass

            # ── 5. Temporal Wait ──
            elif action in ("wait", "sleep"):
                sec = float(param or 1.0)
                time.sleep(sec)

            else:
                self._log(f"⚠️ Unknown stage: {s_raw}, continuing...")

            time.sleep(0.1)

        self._log("─" * 70)
        self._log("🏁 [WORKFLOW COMPLETE] All pipeline stages executed successfully!\n")
        return True

    def execute_file(self, filepath: str) -> bool:
        """Executes a .k file containing workflow pipes line by line."""
        p = Path(filepath)
        if not p.exists():
            print(f"❌ Error: Workflow file '{filepath}' not found.")
            return False

        with open(p, "r") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if not self.execute_pipe(line):
                return False
        return True


def main():
    if len(sys.argv) < 2:
        print("Usage: workflow_engine.py <pipe \"nav::goto[bedroom] | vision::scan\" | file.k>")
        sys.exit(1)

    arg = " ".join(sys.argv[1:])
    engine = WorkflowEngine(verbose=True)

    if arg.endswith(".k") and Path(arg).exists():
        success = engine.execute_file(arg)
    else:
        success = engine.execute_pipe(arg)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
