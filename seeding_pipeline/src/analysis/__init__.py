"""Knowledge discovery analysis modules."""

from .gap_detection import (
    identify_topic_clusters,
    calculate_gap_score,
    detect_structural_gaps,
    run_gap_detection
)

from .missing_links import (
    find_missing_links,
    calculate_connection_potential,
    run_missing_link_analysis
)

from .diversity_metrics import (
    update_diversity_metrics,
    get_diversity_insights,
    run_diversity_analysis
)

from .analysis_orchestrator import (
    run_knowledge_discovery
)

from .semantic_gap_detection import (
    detect_semantic_gaps,
    run_semantic_gap_detection
)