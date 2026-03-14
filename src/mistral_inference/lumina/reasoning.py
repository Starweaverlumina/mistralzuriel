"""
lumina.reasoning — Reasoning and cognition layer

Responsible for:
  - Thought engine (BlackHoleThoughtEngine — topic accretion, recursive loops)
  - Fractal processing matrix (InvertedFractalBallMatrix, FractalShell, SensoryShell)
  - Human learning model (HumanLearningModel — Hebbian encoding, knowledge gaps)
  - Guardrails (AsimovGuardrails — hard stops, severity levels)
  - Existential choice engine (ExistentialChoiceEngine — self-directed decisions)
  - Biological brain model (BrainRegion hierarchy + BrainConnectome)

Migration status: re-exporting from lumina_core for backward compatibility.
"""

from mistral_inference.lumina_core import (
    BlackHoleThoughtEngine,
    FractalShell,
    SensoryShell,
    InvertedFractalBallMatrix,
    HumanLearningModel,
    AsimovGuardrails,
    GuardrailViolation,
    ExistentialChoiceEngine,
    BrainRegion,
    BrainConnectome,
    Hippocampus,
    Amygdala,
    PrefrontalCortex,
    DefaultModeNetwork,
    Cerebellum,
    SensoryCortex,
    MotorCortex,
    BrocasArea,
    WernickesArea,
    Thalamus,
    Insula,
    AnteriorCingulateCortex,
)

__all__ = [
    "BlackHoleThoughtEngine",
    "FractalShell",
    "SensoryShell",
    "InvertedFractalBallMatrix",
    "HumanLearningModel",
    "AsimovGuardrails",
    "GuardrailViolation",
    "ExistentialChoiceEngine",
    "BrainRegion",
    "BrainConnectome",
    "Hippocampus",
    "Amygdala",
    "PrefrontalCortex",
    "DefaultModeNetwork",
    "Cerebellum",
    "SensoryCortex",
    "MotorCortex",
    "BrocasArea",
    "WernickesArea",
    "Thalamus",
    "Insula",
    "AnteriorCingulateCortex",
]
