"""Domain-specific test fixtures for diversity testing."""

from typing import List
from src.core.models import Segment


class DomainFixtures:
    """Test fixtures for multiple podcast domains."""

    @staticmethod
    def technology_podcast_fixture() -> List[Segment]:
        """Technology podcast segments."""
        return [
            Segment(
                id="tech_seg1",
                episode_id="tech_ep1",
                start_time=0.0,
                end_time=60.0,
                text="Today we're discussing the latest developments in artificial intelligence. "
                     "Google's new Gemini model and OpenAI's GPT-4 are pushing the boundaries of what's possible with large language models.",
                speaker="Host"
            ),
            Segment(
                id="tech_seg2",
                episode_id="tech_ep1",
                start_time=60.0,
                end_time=120.0,
                text="Machine learning has revolutionized computer vision. Companies like Tesla are using neural networks "
                     "for autonomous driving, processing millions of images to train their models.",
                speaker="Guest Expert"
            ),
            Segment(
                id="tech_seg3",
                episode_id="tech_ep1",
                start_time=120.0,
                end_time=180.0,
                text="The future of AI lies in multimodal models that can process text, images, and audio simultaneously. "
                     "This convergence will enable more natural human-computer interaction.",
                speaker="Guest Expert"
            )
        ]

    @staticmethod
    def cooking_podcast_fixture() -> List[Segment]:
        """Cooking podcast segments."""
        return [
            Segment(
                id="cook_seg1",
                episode_id="cook_ep1",
                start_time=0.0,
                end_time=60.0,
                text="Welcome to Kitchen Chronicles! Today we're making a classic spaghetti bolognese. "
                     "You'll need pasta, ground beef, tomatoes, onions, and garlic for this Italian favorite.",
                speaker="Chef Host"
            ),
            Segment(
                id="cook_seg2",
                episode_id="cook_ep1",
                start_time=60.0,
                end_time=120.0,
                text="The secret to a great bolognese sauce is letting it simmer for at least 30 minutes. "
                     "This allows the flavors to meld together. Some chefs add a splash of red wine for depth.",
                speaker="Chef Host"
            ),
            Segment(
                id="cook_seg3",
                episode_id="cook_ep1",
                start_time=120.0,
                end_time=180.0,
                text="For a healthier version, you can substitute ground turkey for beef, or use zucchini noodles "
                     "instead of traditional pasta. The cooking time remains about the same.",
                speaker="Chef Host"
            )
        ]

    @staticmethod
    def history_podcast_fixture() -> List[Segment]:
        """History podcast segments."""
        return [
            Segment(
                id="hist_seg1",
                episode_id="hist_ep1",
                start_time=0.0,
                end_time=60.0,
                text="World War II began in 1939 when Nazi Germany invaded Poland. "
                     "Winston Churchill became Prime Minister of the United Kingdom in 1940, leading Britain through its darkest hour.",
                speaker="Historian"
            ),
            Segment(
                id="hist_seg2",
                episode_id="hist_ep1",
                start_time=60.0,
                end_time=120.0,
                text="The Battle of Britain in 1940 was a crucial turning point. The Royal Air Force successfully "
                     "defended the UK against the German Luftwaffe, preventing a planned invasion.",
                speaker="Historian"
            ),
            Segment(
                id="hist_seg3",
                episode_id="hist_ep1",
                start_time=120.0,
                end_time=180.0,
                text="The war ended in 1945 with the surrender of Germany in May and Japan in August. "
                     "The atomic bombs dropped on Hiroshima and Nagasaki hastened Japan's surrender.",
                speaker="Historian"
            )
        ]

    @staticmethod
    def medical_podcast_fixture() -> List[Segment]:
        """Medical/health podcast segments."""
        return [
            Segment(
                id="med_seg1",
                episode_id="med_ep1",
                start_time=0.0,
                end_time=60.0,
                text="Type 2 diabetes affects millions worldwide. It's characterized by insulin resistance, "
                     "where the body doesn't use insulin effectively, leading to elevated blood sugar levels.",
                speaker="Dr. Smith"
            ),
            Segment(
                id="med_seg2",
                episode_id="med_ep1",
                start_time=60.0,
                end_time=120.0,
                text="Managing diabetes requires a combination of medication, diet, and exercise. "
                     "Metformin is often the first-line medication, but lifestyle changes are equally important.",
                speaker="Dr. Smith"
            ),
            Segment(
                id="med_seg3",
                episode_id="med_ep1",
                start_time=120.0,
                end_time=180.0,
                text="Regular monitoring of blood glucose levels is crucial. Patients should aim for an A1C level "
                     "below 7%. Complications can include neuropathy, retinopathy, and cardiovascular disease.",
                speaker="Dr. Smith"
            )
        ]

    @staticmethod
    def arts_culture_podcast_fixture() -> List[Segment]:
        """Arts and culture podcast segments."""
        return [
            Segment(
                id="art_seg1",
                episode_id="art_ep1",
                start_time=0.0,
                end_time=60.0,
                text="Vincent van Gogh's 'The Starry Night' was painted in 1889 while he was at the "
                     "Saint-Paul-de-Mausole asylum. It's now one of the most recognized paintings in the world.",
                speaker="Art Curator"
            ),
            Segment(
                id="art_seg2",
                episode_id="art_ep1",
                start_time=60.0,
                end_time=120.0,
                text="Van Gogh was a key figure in Post-Impressionism, though he sold only one painting during "
                     "his lifetime. His bold colors and emotional intensity influenced countless artists.",
                speaker="Art Curator"
            ),
            Segment(
                id="art_seg3",
                episode_id="art_ep1",
                start_time=120.0,
                end_time=180.0,
                text="'The Starry Night' is housed at the Museum of Modern Art in New York. The swirling sky "
                     "and cypress tree have been interpreted as expressing van Gogh's turbulent mental state.",
                speaker="Art Curator"
            )
        ]