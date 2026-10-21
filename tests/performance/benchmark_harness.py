#!/usr/bin/env python3
"""
GRaCEmo ViRa — Production Real-Time Benchmark Harness & Statistics Engine
Records trace-correlated latency, computes statistical percentiles (P50, P90, P95, P99, MIN, MAX, MEAN, STDDEV),
and analyzes real-time jitter and tail latency across Unit, Component, Integration, and End-to-End tiers.
"""
from __future__ import annotations
import math
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class LatencyTier(str, Enum):
    UNIT = "UNIT"                  # Pure software function execution
    COMPONENT = "COMPONENT"        # Subsystem-to-subsystem (e.g. EventBus -> RobotBridge)
    INTEGRATION = "INTEGRATION"    # RobotBridge -> ROS 2 / Nav2
    E2E = "END_TO_END"             # Full closed loop (Voice -> Motion, Arrival -> Audio)


@dataclass
class BenchmarkRecord:
    timestamp: float
    trace_id: str
    operation: str
    tier: LatencyTier
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencyStats:
    operation: str
    tier: LatencyTier
    count: int
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    mean_ms: float
    stddev_ms: float
    jitter_ms: float       # max - min spread
    outlier_count: int     # count of values > mean + 2*stddev

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "tier": self.tier.value,
            "count": self.count,
            "p50_ms": round(self.p50_ms, 3),
            "p90_ms": round(self.p90_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "mean_ms": round(self.mean_ms, 3),
            "stddev_ms": round(self.stddev_ms, 3),
            "jitter_ms": round(self.jitter_ms, 3),
            "outliers": self.outlier_count,
        }


class BenchmarkHarness:
    """
    Thread-safe benchmark harness for recording real-time latency profiles.
    """

    def __init__(self):
        self._records: List[BenchmarkRecord] = []

    def record(
        self,
        operation: str,
        tier: LatencyTier,
        start_time: float,
        end_time: float,
        trace_id: str = "trace_bench",
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BenchmarkRecord:
        duration_ms = (end_time - start_time) * 1000.0
        rec = BenchmarkRecord(
            timestamp=start_time,
            trace_id=trace_id,
            operation=operation,
            tier=tier,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            success=success,
            error=error,
            metadata=metadata or {},
        )
        self._records.append(rec)
        return rec

    def get_records(self, operation: Optional[str] = None) -> List[BenchmarkRecord]:
        if operation:
            return [r for r in self._records if r.operation == operation]
        return list(self._records)

    def calculate_stats(self, operation: str) -> Optional[LatencyStats]:
        matches = [r for r in self._records if r.operation == operation and r.success]
        if not matches:
            return None

        durations = sorted([r.duration_ms for r in matches])
        n = len(durations)
        tier = matches[0].tier

        def _percentile(p: float) -> float:
            if n == 1:
                return durations[0]
            k = (n - 1) * (p / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return durations[int(k)]
            d0 = durations[int(f)] * (c - k)
            d1 = durations[int(c)] * (k - f)
            return d0 + d1

        mean_val = statistics.mean(durations)
        std_val = statistics.stdev(durations) if n > 1 else 0.0
        outlier_thresh = mean_val + (3.0 * std_val)
        outliers = sum(1 for d in durations if d > outlier_thresh)

        return LatencyStats(
            operation=operation,
            tier=tier,
            count=n,
            p50_ms=_percentile(50.0),
            p90_ms=_percentile(90.0),
            p95_ms=_percentile(95.0),
            p99_ms=_percentile(99.0),
            min_ms=min(durations),
            max_ms=max(durations),
            mean_ms=mean_val,
            stddev_ms=std_val,
            jitter_ms=max(durations) - min(durations),
            outlier_count=outliers,
        )

    def generate_report_table(self) -> str:
        ops = sorted(list({r.operation for r in self._records}))
        lines = [
            "| Tier | Operation | Count | P50 (ms) | P90 (ms) | P95 (ms) | P99 (ms) | Min (ms) | Max (ms) | Mean (ms) | StdDev (ms) | Jitter (ms) | Outliers |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for op in ops:
            stats = self.calculate_stats(op)
            if stats:
                lines.append(
                    f"| {stats.tier.value} | {stats.operation} | {stats.count} | {stats.p50_ms:.3f} | {stats.p90_ms:.3f} | {stats.p95_ms:.3f} | {stats.p99_ms:.3f} | {stats.min_ms:.3f} | {stats.max_ms:.3f} | {stats.mean_ms:.3f} | {stats.stddev_ms:.3f} | {stats.jitter_ms:.3f} | {stats.outlier_count} |"
                )
        return "\n".join(lines)
