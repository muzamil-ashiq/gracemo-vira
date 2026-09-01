#!/usr/bin/env python3
"""Redirects to the full LPU Autonomous Robotics Digital Twin Studio."""

import os
import sys

tools_dir = os.path.dirname(os.path.abspath(__file__))
dt_studio = os.path.join(tools_dir, 'run_digital_twin_studio.py')

if __name__ == '__main__':
    os.execv(sys.executable, [sys.executable, dt_studio] + sys.argv[1:])
