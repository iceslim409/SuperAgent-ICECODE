"""
ICECODE Local Inference Layer
Ruleaza modele mari local cu resurse minime.

Sursa: ICECODE Agent — mecanisme reale, testate in productie.
"""
from .manager import LocalInferenceManager
from .router import LocalModelRouter

__all__ = ["LocalInferenceManager", "LocalModelRouter"]
