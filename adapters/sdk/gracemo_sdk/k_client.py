#!/usr/bin/env python3
"""
GRaCEmo ViRa — K Language Python Client
Connects to the native Rust K engine via the MNSE Kernel HTTP interface (:7780).
Allows Level 4 Cognitive Agents, mission runners, test suites, and CLI operators
to dispatch typed K pipelines to the robot.
"""

import sys
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

DEFAULT_KERNEL_URL = "http://127.0.0.1:7780"


class KClient:
    def __init__(self, kernel_url: str = DEFAULT_KERNEL_URL):
        self.kernel_url = kernel_url.rstrip("/")

    def execute(self, expression: str, timeout_sec: float = 10.0) -> Dict[str, Any]:
        """
        Sends a K expression string to the Rust K engine for parsing, planning, and execution.
        Returns the ExecutionSummary dictionary.
        """
        url = f"{self.kernel_url}/k/execute"
        payload = json.dumps({"expression": expression}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            return {"success": False, "error": f"HTTP {e.code}: {err_body}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_compiled_context(self, fmt: str = "toon") -> str:
        """Retrieves compiled reality from VCSC in TOON, JSON, or K-Pipe format."""
        url = f"{self.kernel_url}/context?format={fmt}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            return f"Error retrieving context: {e}"


def main():
    if len(sys.argv) < 2:
        print("Usage: k_client.py \"<k expression>\"")
        print("Example: k_client.py \"graph::locate[entity: 'Coke'] | nav::reach\"")
        sys.exit(1)

    expr = sys.argv[1]
    client = KClient()
    print(f"[K CLIENT] Dispatching: {expr}")
    result = client.execute(expr)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
