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