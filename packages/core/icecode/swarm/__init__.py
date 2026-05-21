"""ICECODE Swarm — multi-agent orchestration engine."""
from .coordinator import SwarmCoordinator
from .worker import SwarmWorker
from .pipeline import run_pipeline
from .parallel import run_parallel

__all__ = ["SwarmCoordinator", "SwarmWorker", "run_pipeline", "run_parallel"]
