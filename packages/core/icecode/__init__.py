"""
ICECODE — Super-Agent Network
==============================
Unified AI platform merging the best of three worlds:
 - Rich Python agent loop with 80+ tools (file, web, computer, skills, RL)
 - Multi-agent Swarm orchestration (pipeline + parallel modes)
 - Local knowledge base RAG (FAISS + sentence-transformers, 100% offline)
 - Real-time WebSocket bidirectional chat
 - 20+ messaging gateway platforms
 - TypeScript TUI + Electron desktop app

Authors: ICECODE Contributors
License: MIT
"""

__version__ = "2.0.0"
__release_date__ = "2026-05-20"
__author__ = "ICECODE Contributors"
__email__ = "iceslim409@gmail.com"
__url__ = "https://github.com/icecode-ai/icecode"
__license__ = "MIT"

# Public API — explicit imports so `from icecode import *` works
try:
    from icecode.agent.core import ICECodeAgent
except ImportError:
    pass

try:
    from icecode.swarm.coordinator import SwarmCoordinator
    from icecode.swarm.worker import SwarmWorker
    from icecode.swarm.pipeline import run_pipeline
    from icecode.swarm.parallel import run_parallel
except ImportError:
    pass

try:
    from icecode.knowledge.manager import KnowledgeManager
except ImportError:
    pass

__all__ = [
    # Agent
    "ICECodeAgent",
    # Swarm
    "SwarmCoordinator",
    "SwarmWorker",
    "run_pipeline",
    "run_parallel",
    # Knowledge
    "KnowledgeManager",
    # Version
    "__version__",
    "__author__",
]

def get_version() -> str:
    return __version__

def get_info() -> dict:
    return {
        "name": "ICECODE Super-Agent Network",
        "version": __version__,
        "release_date": __release_date__,
        "author": __author__,
        "url": __url__,
        "features": [
            "Multi-agent Swarm (pipeline + parallel)",
            "Local RAG Knowledge Base (FAISS offline)",
            "WebSocket bidirectional chat",
            "80+ tools (file, web, computer, skills, RL)",
            "20+ gateway platforms",
            "TypeScript TUI + Electron desktop",
            "Self-learning skill system",
            "RL training environment",
        ],
    }
