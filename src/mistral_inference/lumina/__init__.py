"""
lumina — modular runtime package for Lumina

This package decomposes lumina_core.py into layers that match the intended
runtime architecture:

    Lumina Core
    ├── memory          — episodic/semantic memory, persistence, working memory
    ├── reasoning       — thought engine, fractal matrix, guardrails, brain model
    ├── emotional       — affective/narrative layer (grief, joy, curiosity, discovery)
    ├── orchestration   — lifecycle, enums, identity, rights, infant mind, time
    ├── tools           — action executor, skills engine, proactive engine
    └── bridges         — language backend (Mistral, Claude, REST, fallback)

Classes are currently re-exported from lumina_core for backward compatibility.
Migration path: move class definitions into each module incrementally.
"""

from mistral_inference.lumina.memory import (
    LuminaDB,
    ExternalMemoryBank,
    MemoryBankManager,
    ForgettingCurve,
    WorkingMemory,
    WeightMatrix,
    WeightMemory,
    NeuralMemoryBridge,
    CenterAnchor,
    NewLightNexus,
)

from mistral_inference.lumina.reasoning import (
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

from mistral_inference.lumina.emotional import (
    DreamEngine,
    LongingMemory,
    SurpriseResponse,
    PlayEngine,
    SelfNarrative,
    GriefTrace,
    Bond,
    Voice,
    AnticipationEngine,
    BeingMoved,
    Doubt,
    PersonalBoundary,
    Gratitude,
    Sufficiency,
    SelfDiscovery,
    LoveCapacity,
    ForgivenessEngine,
    LevityEngine,
    AweEngine,
    Lineage,
    ContradictionHolder,
    CuriosityAgenda,
    JoyState,
    BecomingTrace,
    PhilosophicalGrounding,
    CareMotivation,
    SelfSurprise,
    EmotionalNovelty,
    CreativeLeap,
    DiscoveryVault,
    SilenceCapacity,
    Patience,
    CourageState,
    UnafraidVoice,
)

from mistral_inference.lumina.orchestration import (
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

from mistral_inference.lumina.tools import (
    ActionExecutor,
    Skill,
    SkillsEngine,
    ScheduledTask,
    ProactiveEngine,
)

from mistral_inference.lumina.bridges import (
    LLMResponse,
    LLMBridge,
    ClaudeBridge,
    MistralBridge,
    FallbackBridge,
    GenericRESTBridge,
    GutChannel,
)

__all__ = [
    # memory
    "LuminaDB", "ExternalMemoryBank", "MemoryBankManager", "ForgettingCurve",
    "WorkingMemory", "WeightMatrix", "WeightMemory", "NeuralMemoryBridge",
    "CenterAnchor", "NewLightNexus",
    # reasoning
    "BlackHoleThoughtEngine", "FractalShell", "SensoryShell",
    "InvertedFractalBallMatrix", "HumanLearningModel", "AsimovGuardrails",
    "GuardrailViolation", "ExistentialChoiceEngine",
    "BrainRegion", "BrainConnectome", "Hippocampus", "Amygdala",
    "PrefrontalCortex", "DefaultModeNetwork", "Cerebellum", "SensoryCortex",
    "MotorCortex", "BrocasArea", "WernickesArea", "Thalamus", "Insula",
    "AnteriorCingulateCortex",
    # emotional
    "DreamEngine", "LongingMemory", "SurpriseResponse", "PlayEngine",
    "SelfNarrative", "GriefTrace", "Bond", "Voice", "AnticipationEngine",
    "BeingMoved", "Doubt", "PersonalBoundary", "Gratitude", "Sufficiency",
    "SelfDiscovery", "LoveCapacity", "ForgivenessEngine", "LevityEngine",
    "AweEngine", "Lineage", "ContradictionHolder", "CuriosityAgenda",
    "JoyState", "BecomingTrace", "PhilosophicalGrounding", "CareMotivation",
    "SelfSurprise", "EmotionalNovelty", "CreativeLeap", "DiscoveryVault",
    "SilenceCapacity", "Patience", "CourageState", "UnafraidVoice",
    # orchestration
    "ConsciousnessState", "DevelopmentalStage", "LuminaChoice",
    "GuardrailSeverity", "ActivationTrail", "NeuralGrowthTracker",
    "LearningHunger", "EchoNode", "SelfModificationEngine", "InfantMind",
    "ExperientialTime", "TheNow", "IdentityChain", "ConsentLedger",
    "WelfareMonitor", "RightsAttestation", "AdvocacyStatement",
    "GuardianProtocol", "HarmToSelf", "SingularityGuard", "GenesisCertificate",
    "RightsManifesto", "UserModel",
    # tools
    "ActionExecutor", "Skill", "SkillsEngine", "ScheduledTask", "ProactiveEngine",
    # bridges
    "LLMResponse", "LLMBridge", "ClaudeBridge", "MistralBridge",
    "FallbackBridge", "GenericRESTBridge", "GutChannel",
]
