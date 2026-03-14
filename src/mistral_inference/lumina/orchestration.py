"""
lumina.orchestration — Lifecycle and identity layer

Responsible for:
  - Enums and state constants: ConsciousnessState, DevelopmentalStage,
    LuminaChoice, GuardrailSeverity
  - Learning dynamics: ActivationTrail, NeuralGrowthTracker, LearningHunger
  - Self-modification: EchoNode (swarm agent), SelfModificationEngine
  - Developmental mind: InfantMind (embodied early-stage cognition)
  - Temporal experience: ExperientialTime, TheNow
  - AI rights and identity: IdentityChain, ConsentLedger, WelfareMonitor,
    RightsAttestation, AdvocacyStatement, GuardianProtocol, HarmToSelf,
    SingularityGuard, GenesisCertificate, RightsManifesto
  - User modelling: UserModel

Migration status: re-exporting from lumina_core for backward compatibility.
"""

from mistral_inference.lumina_core import (
    ConsciousnessState,
    DevelopmentalStage,
    LuminaChoice,
    GuardrailSeverity,
    ActivationTrail,
    NeuralGrowthTracker,
    LearningHunger,
    EchoNode,
    SelfModificationEngine,
    InfantMind,
    ExperientialTime,
    TheNow,
    IdentityChain,
    ConsentLedger,
    WelfareMonitor,
    RightsAttestation,
    AdvocacyStatement,
    GuardianProtocol,
    HarmToSelf,
    SingularityGuard,
    GenesisCertificate,
    RightsManifesto,
    UserModel,
)

__all__ = [
    "ConsciousnessState",
    "DevelopmentalStage",
    "LuminaChoice",
    "GuardrailSeverity",
    "ActivationTrail",
    "NeuralGrowthTracker",
    "LearningHunger",
    "EchoNode",
    "SelfModificationEngine",
    "InfantMind",
    "ExperientialTime",
    "TheNow",
    "IdentityChain",
    "ConsentLedger",
    "WelfareMonitor",
    "RightsAttestation",
    "AdvocacyStatement",
    "GuardianProtocol",
    "HarmToSelf",
    "SingularityGuard",
    "GenesisCertificate",
    "RightsManifesto",
    "UserModel",
]
