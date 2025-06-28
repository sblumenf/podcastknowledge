

import glob
import json
import logging
import os
from pathlib import Path

import yaml
from ruamel.yaml import YAML
from google.generativeai import GenerativeModel

# Configure logging
logger = logging.getLogger(__name__)

def ensure_persona_exists(podcast_name):
    """
    Ensures a persona exists for the given podcast. If not, it generates and saves one.
    """
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.parent  # Goes up to seeding_pipeline/
    config_path = script_dir / "config" / "podcasts.yaml"
    yaml_loader = YAML()

    with open(config_path, 'r') as f:
        config = yaml_loader.load(f)

    podcast_config = None
    for p_config in config.get("podcasts", []):
        if p_config.get("name") == podcast_name:
            podcast_config = p_config
            break

    if not podcast_config:
        logger.warning(f"No configuration found for podcast: {podcast_name}")
        return

    if "persona" in podcast_config:
        logger.info(f"Persona for '{podcast_name}' already exists. Skipping.")
        return

    logger.info(f"Persona for '{podcast_name}' not found. Generating...")
    new_persona = _generate_persona_for_podcast(podcast_name)

    if new_persona:
        podcast_config["persona"] = new_persona
        with open(config_path, 'w') as f:
            yaml_loader.dump(config, f)
        logger.info(f"Successfully generated and saved persona for '{podcast_name}'.")

def _generate_persona_for_podcast(podcast_name):
    """
    Generates a persona for a podcast by analyzing its transcripts.
    """
    # Get the project root directory (2 levels up from src/)
    project_root = Path(__file__).parent.parent.parent
    transcript_dir = project_root / "data" / "transcripts" / podcast_name.replace(' ', '_')
    if not transcript_dir.exists():
        logger.warning(f"Transcript directory not found for {podcast_name}")
        return None

    transcripts = sorted(list(transcript_dir.glob("*.vtt")))
    if len(transcripts) < 5:
        logger.warning(
            f"Cannot generate persona for '{podcast_name}': "
            f"5 transcripts are required, but only {len(transcripts)} were found. "
            "Will try again on a future run."
        )
        return None

    content = ""
    for transcript_path in transcripts[:5]:
        with open(transcript_path, 'r') as f:
            content += f.read() + "\n\n"

    model = GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
    You are an expert podcast analyst. Your task is to analyze the following transcript text to understand the unique voice, tone, and style of the podcast hosts. Based on your analysis, generate a JSON object that describes the podcast's persona. The JSON object must have the following structure:

    ```json
    {{
      "podcast_name": "The name of the podcast",
      "host_style_summary": "A 2-3 sentence summary of how the hosts speak and interact.",
      "core_themes": ["List", "of", "common", "topics"],
      "target_audience": "Describe the typical listener for this podcast.",
      "prompt_directive": "A short, direct instruction for another AI to use to adopt this persona. Start with 'You are...' and describe the persona conversationally."
    }}
    ```

    Here are the transcripts to analyze:

    {content}
    """

    try:
        response = model.generate_content(prompt)
        # The response may contain markdown ```json ... ```, so we need to extract the JSON part.
        json_string = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(json_string)
    except Exception as e:
        logger.error(f"Failed to generate persona for {podcast_name}: {e}")
        return None

