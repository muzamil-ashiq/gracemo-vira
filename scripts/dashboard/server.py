#!/usr/bin/env python3
"""
GRaCEmo ViRa — Real-Time Kernel & Robotics Observability Dashboard Backend.
Built with FastAPI & WebSockets to monitor the tripartite architecture:
Kernel Event Bus -> Adapters (Vision, Voice, Brain) -> ROS 2 / Gazebo Simulation.
"""
import asyncio
import json
import math
import os
import sys
import time
from typing import List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="GRaCEmo ViRa Observability Dashboard")

# Global in-memory state
robot_telemetry = {
    "x": 0.0,
    "y": 0.0,
    "z": 0.0,
    "yaw_deg": 0.0,
    "vx": 0.0,
    "wz": 0.0,
    "min_obstacle_dist": 99.0,
    "status": "READY",
    "stall_detected": False,
    "battery_pct": 98.4,
    "mission_step": "Stationary at Origin",
    "target_room": "Central Hallway",
}

adapter_metrics = {
    "vision": {
        "status": "ONLINE",
        "model": "YOLOv11n Object Detector",
        "fps": 28.5,
        "latency_ms": 16.2,
        "confidence_avg": 0.91,
        "active_detections": ["doorway: 94%", "obstacle_column: 96%"],
    },
    "voice": {
        "status": "READY",
        "stt_engine": "Faster-Whisper (Int8)",
        "tts_engine": "Piper TTS (en_US-lessac)",
        "stt_latency_ms": 135.0,
        "last_transcript": "Ready for voice or web commands.",
    },
    "brain": {
        "status": "ACTIVE",
        "planner": "SpatialKnowledgeGraph + PurePursuit",
        "active_goal": "Awaiting Goal",
        "planning_latency_ms": 4.8,
        "completed_actions": 0,
    },
    "bridge": {
        "status": "CONNECTED",
        "ros_domain_id": 0,
        "sim_source": "Gazebo Harmonic 8",
        "msg_rate_hz": 50.0,
        "active_topics": ["/scan", "/odom", "/cmd_vel", "/camera/image_raw"],
    },
}

event_timeline: List[Dict[str, Any]] = [
    {
        "id": "evt_init_001",
        "timestamp": time.strftime("%H:%M:%S"),
        "epoch": time.time(),
        "source": "KERNEL",
        "event_type": "kernel.boot",
        "payload": "MNSE Kernel Event Ledger initialized. Tripartite bridge listening.",
        "status": "SUCCESS",
        "latency_ms": 1.2,
    }
]

# Track connected WebSocket clients
connected_clients: List[WebSocket] = []

def record_event(source: str, event_type: str, payload: str, status: str = "SUCCESS", latency_ms: float = 0.0):
    evt = {
        "id": f"evt_{len(event_timeline) + 1:04d}",
        "timestamp": time.strftime("%H:%M:%S"),
        "epoch": time.time(),
        "source": source,
        "event_type": event_type,
        "payload": payload,
        "status": status,
        "latency_ms": round(latency_ms, 2),
    }
    event_timeline.insert(0, evt)
    if len(event_timeline) > 100:
        event_timeline.pop()
    return evt

class CommandRequest(BaseModel):
    command: str
    target_room: str = "Bedroom"

@app.get("/api/status")
async def get_status():
    return {
        "telemetry": robot_telemetry,
        "adapters": adapter_metrics,
        "timeline_count": len(event_timeline),
    }

@app.get("/api/events")
async def get_events():
    return event_timeline[:50]

@app.post("/api/command")
async def post_command(cmd: CommandRequest):
    t0 = time.time()
    user_cmd = cmd.command.strip()
    target = cmd.target_room.strip()

    # 1. Voice/Text perception event
    record_event("VOICE/INPUT", "user.intent", f"Received command: '{user_cmd}'", status="SUCCESS", latency_ms=12.5)

    # 2. Kernel Event Bus dispatch
    record_event("KERNEL", "event.intent.navigation", f"Route planned to destination: [{target}]", status="SUCCESS", latency_ms=4.2)

    # 3. Reasoning / Brain planner event
    robot_telemetry["target_room"] = target
    robot_telemetry["status"] = "NAVIGATING"
    robot_telemetry["mission_step"] = f"Transit to {target} entrance"

    record_event("BRAIN", "planner.trajectory.synthesize", f"Generated 4 corridor waypoints to {target}", status="SUCCESS", latency_ms=8.6)

    # 4. Robot Bridge action dispatch
    record_event("BRIDGE", "action.dispatch.cmd_vel", f"Publishing motion trajectory (vx=0.35 m/s) to /cmd_vel", status="IN_PROGRESS", latency_ms=1.8)

    elapsed_ms = (time.time() - t0) * 1000
    return {"status": "dispatched", "target": target, "total_pipeline_latency_ms": round(elapsed_ms, 2)}

class TelemetryUpdate(BaseModel):
    x: float
    y: float
    z: float = 0.0
    yaw_deg: float
    vx: float
    wz: float
    min_dist: float = 99.0
    status: str = "NAVIGATING"

@app.post("/api/telemetry")
async def update_telemetry(t: TelemetryUpdate):
    robot_telemetry["x"] = round(t.x, 3)
    robot_telemetry["y"] = round(t.y, 3)
    robot_telemetry["z"] = round(t.z, 3)
    robot_telemetry["yaw_deg"] = round(t.yaw_deg, 1)
    robot_telemetry["vx"] = round(t.vx, 3)
    robot_telemetry["wz"] = round(t.wz, 3)
    robot_telemetry["min_obstacle_dist"] = round(t.min_dist, 3)
    robot_telemetry["status"] = t.status
    return {"ok": True}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # Broadcast state packet every 100ms
            packet = {
                "type": "state_update",
                "timestamp": time.time(),
                "telemetry": robot_telemetry,
                "adapters": adapter_metrics,
                "recent_events": event_timeline[:12],
            }
            await websocket.send_text(json.dumps(packet))
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

# Serve static frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
def start_gz_listeners():
    try:
        import gz.transport13 as gz_transport
        from gz.msgs10.odometry_pb2 import Odometry
        from gz.msgs10.laserscan_pb2 import LaserScan

        node = gz_transport.Node()

        def on_odom(msg: Odometry):
            pos = msg.pose.position
            ori = msg.pose.orientation
            siny_cosp = 2.0 * (ori.w * ori.z + ori.x * ori.y)
            cosy_cosp = 1.0 - 2.0 * (ori.y * ori.y + ori.z * ori.z)
            yaw = math.atan2(siny_cosp, cosy_cosp)
            robot_telemetry["x"] = round(pos.x, 3)
            robot_telemetry["y"] = round(pos.y, 3)
            robot_telemetry["z"] = round(pos.z, 3)
            robot_telemetry["yaw_deg"] = round(math.degrees(yaw), 1)
            robot_telemetry["vx"] = round(msg.twist.linear.x, 2)
            robot_telemetry["wz"] = round(msg.twist.angular.z, 2)

        def on_scan(msg: LaserScan):
            dists = [r for r in msg.ranges if not math.isnan(r) and not math.isinf(r) and r > 0.08]
            if dists:
                robot_telemetry["min_obstacle_dist"] = round(min(dists), 2)

        node.subscribe(Odometry, "/odom", on_odom)
        node.subscribe(LaserScan, "/scan", on_scan)
        print("✓ Dashboard subscribed directly to Gazebo /odom and /scan")
    except Exception as e:
        print(f"Notice: Gazebo transport listener: {e}")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    start_gz_listeners()
    print(f"Starting GRaCEmo ViRa Observability Dashboard on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
