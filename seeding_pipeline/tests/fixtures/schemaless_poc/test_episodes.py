"""
Test episodes for Phase 1.4 - Proof of Concept Testing.

This module defines 5 diverse podcast episodes from different domains
to test SimpleKGPipeline's extraction capabilities.
"""

from typing import List, Dict, Any
import json
# Define diverse test episodes representing different domains
TEST_EPISODES = [
    {
        "id": "tech_001",
        "domain": "Technology", 
        "title": "The Future of AI and Machine Learning",
        "description": "Discussion about emerging AI technologies and their impact",
        "speakers": ["Dr. Sarah Chen", "Mike Johnson"],
        "transcript_sample": """
        Dr. Sarah Chen: Welcome to Tech Talks. Today we're exploring how artificial intelligence 
        is revolutionizing healthcare. Machine learning algorithms can now detect cancer earlier 
        than traditional methods.
        
        Mike Johnson: That's fascinating, Sarah. I recently read that Google's DeepMind has made 
        significant breakthroughs in protein folding prediction. This could accelerate drug discovery.
        
        Dr. Sarah Chen: Absolutely. The AlphaFold system has solved a 50-year-old biology challenge. 
        It predicts 3D protein structures with remarkable accuracy. This opens doors for treating 
        diseases like Alzheimer's and Parkinson's.
        
        Mike Johnson: What about the ethical considerations? How do we ensure AI in healthcare 
        remains transparent and unbiased?
        
        Dr. Sarah Chen: Great question. We need robust governance frameworks. The EU's AI Act 
        is a step in the right direction, classifying medical AI as high-risk systems requiring 
        strict oversight.
        """,
        "expected_entities": ["Person", "Organization", "Technology", "Disease", "Regulation"],
        "expected_relations": ["DISCUSSES", "WORKS_ON", "TREATS", "REGULATES"]
    },
    
    {
        "id": "business_001",
        "domain": "Business",
        "title": "Startup Strategies in Post-Pandemic Economy",
        "description": "Entrepreneurs discuss adaptation and growth strategies",
        "speakers": ["Lisa Wang", "John Davis"],
        "transcript_sample": """
        Lisa Wang: Welcome back to Startup Stories. I'm here with John Davis, CEO of CloudScale, 
        a company that pivoted during the pandemic from office software to remote collaboration tools.
        
        John Davis: Thanks for having me, Lisa. Yes, when COVID-19 hit, we saw our enterprise 
        clients struggling with remote work. We quickly pivoted our product roadmap.
        
        Lisa Wang: Your revenue grew 300% in 2021. What was the key to this growth?
        
        John Davis: Customer feedback drove everything. We implemented daily standups with our 
        top 10 clients. This helped us ship features they actually needed, not what we thought 
        they needed.
        
        Lisa Wang: You also raised a $50 million Series B from Sequoia Capital last quarter. 
        How are you planning to use this funding?
        
        John Davis: We're focusing on three areas: expanding to Asian markets, particularly 
        Singapore and Japan, hiring 100 engineers, and acquiring smaller competitors to 
        consolidate the market.
        """,
        "expected_entities": ["Person", "Company", "Product", "Location", "Money", "Event"],
        "expected_relations": ["CEO_OF", "RAISED_FUNDING", "EXPANDED_TO", "ACQUIRED"]
    },
    
    {
        "id": "health_001",
        "domain": "Health & Wellness",
        "title": "Mental Health in the Digital Age",
        "description": "Psychologists discuss impact of social media on mental health",
        "speakers": ["Dr. Emily Rodriguez", "Dr. James Park"],
        "transcript_sample": """
        Dr. Emily Rodriguez: Today on Mind Matters, we're discussing how social media affects 
        teenage mental health. Dr. Park, your recent study at Stanford University showed some 
        alarming trends.
        
        Dr. James Park: Yes, Emily. We studied 5,000 teenagers over three years. Those spending 
        more than 4 hours daily on platforms like Instagram and TikTok showed 40% higher rates 
        of anxiety and depression.
        
        Dr. Emily Rodriguez: What mechanisms drive this correlation?
        
        Dr. James Park: Three main factors: social comparison, fear of missing out (FOMO), and 
        disrupted sleep patterns. The constant stream of curated content creates unrealistic 
        expectations.
        
        Dr. Emily Rodriguez: Are there any positive aspects? Some argue these platforms provide 
        community and support.
        
        Dr. James Park: Absolutely. We found that teenagers using social media for creative 
        expression or connecting with support groups showed improved mental health outcomes. 
        It's about intentional, mindful usage rather than passive scrolling.
        """,
        "expected_entities": ["Person", "University", "Study", "Platform", "Condition", "Behavior"],
        "expected_relations": ["CONDUCTED_STUDY", "AFFECTS", "CAUSES", "IMPROVES"]
    },
    
    {
        "id": "arts_001",
        "domain": "Arts & Culture",
        "title": "Renaissance Art in Modern Context",
        "description": "Art historians discuss influence of Renaissance on contemporary art",
        "speakers": ["Prof. Maria Gonzalez", "Tom Mitchell"],
        "transcript_sample": """
        Prof. Maria Gonzalez: Welcome to Art History Today. I'm speaking with Tom Mitchell, 
        curator at the Metropolitan Museum of Art, about their new exhibition "Digital Renaissance."
        
        Tom Mitchell: Thank you, Maria. This exhibition explores how contemporary digital artists 
        are reinterpreting Renaissance masterpieces. For example, Refik Anadol's AI installation 
        reimagines Botticelli's "Birth of Venus" using machine learning algorithms.
        
        Prof. Maria Gonzalez: How does this connect to the original Renaissance ideals of humanism 
        and scientific inquiry?
        
        Tom Mitchell: The Renaissance masters like Leonardo da Vinci merged art with science. 
        Today's digital artists continue this tradition, using code as their canvas. Casey Reas, 
        co-creator of Processing programming language, creates generative art inspired by 
        Renaissance mathematical principles.
        
        Prof. Maria Gonzalez: The exhibition also features NFT artworks. How does blockchain 
        technology relate to Renaissance patronage systems?
        
        Tom Mitchell: It's fascinating. Just as the Medici family commissioned works from 
        Michelangelo, today's crypto collectors are the new patrons, supporting digital artists 
        through NFT purchases.
        """,
        "expected_entities": ["Person", "Museum", "Artwork", "Artist", "Technology", "Movement"],
        "expected_relations": ["CURATOR_AT", "CREATED", "INSPIRED_BY", "PATRONIZES"]
    },
    
    {
        "id": "science_001",
        "domain": "Science",
        "title": "Climate Change and Ocean Ecosystems",
        "description": "Marine biologists discuss impact of warming oceans",
        "speakers": ["Dr. Alan Foster", "Dr. Nina Patel"],
        "transcript_sample": """
        Dr. Alan Foster: On today's Ocean Science podcast, we're discussing our expedition to 
        the Great Barrier Reef with Dr. Nina Patel from the Marine Biology Institute.
        
        Dr. Nina Patel: Thanks, Alan. Our team documented the most severe coral bleaching event 
        in recorded history. Water temperatures reached 32°C, causing 75% of surveyed corals to 
        expel their symbiotic algae.
        
        Dr. Alan Foster: What are the cascading effects on the ecosystem?
        
        Dr. Nina Patel: The impacts are devastating. We're seeing population crashes in 
        parrotfish and butterflyfish species that depend on coral. This affects the entire 
        food web, from small invertebrates to apex predators like reef sharks.
        
        Dr. Alan Foster: Your team is testing coral restoration techniques. Can you elaborate?
        
        Dr. Nina Patel: We're developing heat-resistant coral strains through selective breeding. 
        Our lab at James Cook University has created hybrids that survive 2°C higher temperatures. 
        We're also experimenting with 3D-printed calcium carbonate structures to provide new 
        coral habitats.
        
        Dr. Alan Foster: How long before we see results?
        
        Dr. Nina Patel: Coral growth is slow. We estimate 10-15 years before restored reefs 
        become self-sustaining. But without immediate action on carbon emissions, even these 
        efforts may not be enough.
        """,
        "expected_entities": ["Person", "Location", "Species", "Institution", "Phenomenon", "Technology"],
        "expected_relations": ["STUDIES", "LOCATED_AT", "AFFECTS", "DEVELOPS", "THREATENS"]
    }
]


def get_test_episodes() -> List[Dict[str, Any]]:
    """Get the list of test episodes for POC testing."""
    return TEST_EPISODES


def save_test_episodes():
    """Save test episodes to JSON file for reference."""
    output_path = "test_episodes.json"
    with open(output_path, 'w') as f:
        json.dump(TEST_EPISODES, f, indent=2)
    print(f"Saved {len(TEST_EPISODES)} test episodes to {output_path}")


def create_comparison_template() -> Dict[str, Any]:
    """Create a template for comparing extraction results."""
    return {
        "episode_id": "",
        "domain": "",
        "simplekgpipeline_extraction": {
            "entities": [],
            "relations": [],
            "properties": {},
            "processing_time": 0,
            "errors": []
        },
        "current_system_extraction": {
            "speakers": [],
            "topics": [],
            "quotes": [],
            "concepts": [],
            "segments": [],
            "processing_time": 0
        },
        "comparison": {
            "entity_coverage": {
                "expected_found": [],
                "expected_missing": [],
                "unexpected_found": []
            },
            "relation_coverage": {
                "expected_found": [],
                "expected_missing": [],
                "unexpected_found": []
            },
            "gaps_identified": [
                "Timestamp preservation",
                "Speaker attribution",
                "Quote boundaries",
                "Segment context"
            ]
        }
    }


if __name__ == "__main__":
    # Save test episodes for reference
    save_test_episodes()
    
    # Print summary
    print("\n=== Test Episodes Summary ===")
    for episode in TEST_EPISODES:
        print(f"\nDomain: {episode['domain']}")
        print(f"Title: {episode['title']}")
        print(f"Expected Entities: {', '.join(episode['expected_entities'])}")
        print(f"Expected Relations: {', '.join(episode['expected_relations'])}")