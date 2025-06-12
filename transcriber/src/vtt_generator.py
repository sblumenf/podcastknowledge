"""VTT Generator for Podcast Transcription Pipeline.

This module handles the generation of properly formatted WebVTT files
with metadata, speaker voice tags, and proper encoding.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from src.utils.logging import get_logger
from src.checkpoint_recovery import CheckpointManager

logger = get_logger('vtt_generator')


@dataclass
class VTTMetadata:
    """Metadata to be embedded in VTT file."""
    podcast_name: str
    episode_title: str
    publication_date: Union[str, datetime]
    duration: Optional[str] = None
    host: Optional[str] = None
    guests: Optional[List[str]] = None
    description: Optional[str] = None
    youtube_url: Optional[str] = None
    transcription_date: Optional[str] = None
    speakers: Optional[Dict[str, str]] = None
    
    def to_note_block(self) -> str:
        """Convert metadata to VTT NOTE block format."""
        lines = ["NOTE"]
        lines.append(f"Podcast: {self.podcast_name}")
        lines.append(f"Episode: {self.episode_title}")
        # Format date appropriately
        if isinstance(self.publication_date, datetime):
            date_str = self.publication_date.strftime('%Y-%m-%d')
        else:
            date_str = str(self.publication_date)
        lines.append(f"Date: {date_str}")
        
        if self.duration:
            lines.append(f"Duration: {self.duration}")
        
        if self.host:
            lines.append(f"Host: {self.host}")
        
        if self.guests:
            lines.append(f"Guests: {', '.join(self.guests)}")
        
        if self.description:
            # Wrap long descriptions at 80 characters
            desc_lines = self._wrap_text(f"Description: {self.description}", 80)
            lines.extend(desc_lines)
        
        if self.youtube_url:
            lines.append(f"YouTube: {self.youtube_url}")
        
        if self.transcription_date:
            lines.append(f"Transcribed: {self.transcription_date}")
        
        # Add JSON metadata block
        lines.append("")
        lines.append("NOTE JSON Metadata")
        json_data = {
            "podcast": self.podcast_name,
            "episode": self.episode_title,
            "date": date_str,  # Use the formatted date string
            "duration": self.duration,
            "host": self.host,
            "guests": self.guests,
            "description": self.description,
            "youtube_url": self.youtube_url,
            "speakers": self.speakers,
            "transcription_date": self.transcription_date
        }
        # Remove None values for cleaner JSON, but always keep description and youtube_url
        json_data = {k: v for k, v in json_data.items() if v is not None or k in ['description', 'youtube_url']}
        lines.append(json.dumps(json_data, indent=2))
        
        return '\n'.join(lines)
    
    def _wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to specified width, preserving word boundaries."""
        if len(text) <= width:
            return [text]
        
        words = text.split()
        lines = []
        current_line: List[str] = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            if current_length + word_length + len(current_line) > width and current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
            else:
                current_line.append(word)
                current_length += word_length
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines


class VTTGenerator:
    """Generates WebVTT files from transcribed content."""
    
    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None):
        """Initialize VTT generator.
        
        Args:
            checkpoint_manager: Optional checkpoint manager for recovery
        """
        self.encoding = 'utf-8'
        self.checkpoint_manager = checkpoint_manager
        # Characters that need escaping in VTT
        self.escape_chars = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;'
        }
    
    def generate_vtt(self,
                    vtt_content: str,
                    metadata: VTTMetadata,
                    output_path: Optional[Path] = None) -> str:
        """Generate complete VTT file with metadata.
        
        Args:
            vtt_content: VTT-formatted transcript content
            metadata: Metadata to embed in the file
            output_path: Optional path to save the file
            
        Returns:
            Complete VTT file content
        """
        # Build complete VTT file
        vtt_lines = []
        
        # VTT header
        vtt_lines.append("WEBVTT")
        vtt_lines.append("")
        
        # Add metadata as NOTE blocks
        vtt_lines.append(metadata.to_note_block())
        vtt_lines.append("")
        
        # Add style block for speaker formatting (optional)
        style_block = self._generate_style_block(metadata.speakers)
        if style_block:
            vtt_lines.append(style_block)
            vtt_lines.append("")
        
        # Process and add transcript content
        processed_content = self._process_vtt_content(vtt_content)
        vtt_lines.append(processed_content)
        
        # Join all parts
        complete_vtt = '\n'.join(vtt_lines)
        
        # Ensure proper line endings
        complete_vtt = self._normalize_line_endings(complete_vtt)
        
        # Save to file if path provided
        if output_path:
            self._save_vtt_file(complete_vtt, output_path)
        
        return complete_vtt
    
    def _generate_style_block(self, speakers: Optional[Dict[str, str]]) -> Optional[str]:
        """Generate CSS style block for speaker formatting.
        
        Args:
            speakers: Dictionary of speaker mappings
            
        Returns:
            STYLE block content or None
        """
        if not speakers:
            return None
        
        # Generate different colors for speakers
        colors = [
            "#3498db",  # Blue for first speaker (typically host)
            "#2ecc71",  # Green for second speaker
            "#e74c3c",  # Red for third speaker
            "#f39c12",  # Orange for fourth speaker
            "#9b59b6",  # Purple for additional speakers
        ]
        
        style_lines = ["STYLE"]
        
        for i, (label, name) in enumerate(speakers.items()):
            color = colors[i % len(colors)]
            # Escape special characters in CSS selector
            safe_name = name.replace(' ', '\\ ').replace('(', '\\(').replace(')', '\\)')
            style_lines.append(f"::cue(v[voice=\"{safe_name}\"]) {{")
            style_lines.append(f"  color: {color};")
            style_lines.append("}")
        
        return '\n'.join(style_lines)
    
    def _process_vtt_content(self, content: str) -> str:
        """Process VTT content for proper formatting and escaping.
        
        Args:
            content: Raw VTT content
            
        Returns:
            Processed VTT content
        """
        # Split into lines for processing
        lines = content.strip().split('\n')
        processed_lines = []
        
        in_cue_text = False
        
        for line in lines:
            # Skip the WEBVTT header if it exists (we add our own)
            if line.strip().upper() == 'WEBVTT':
                continue
            
            # Skip existing NOTE blocks (we add our own metadata)
            if line.strip().startswith('NOTE'):
                in_note = True
                continue
            
            # Check if this is a timestamp line
            if '-->' in line and self._is_timestamp_line(line):
                processed_lines.append(line)
                in_cue_text = True
                continue
            
            # Process cue text
            if in_cue_text:
                if line.strip() == '':
                    # End of cue
                    processed_lines.append('')
                    in_cue_text = False
                else:
                    # Escape special characters in cue text
                    processed_line = self._escape_cue_text(line)
                    processed_lines.append(processed_line)
            else:
                # Other content (should be minimal after our processing)
                if line.strip():
                    processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def _escape_cue_text(self, text: str) -> str:
        """Escape special characters in cue text.
        
        Args:
            text: Raw cue text
            
        Returns:
            Escaped cue text
        """
        # Don't escape within voice tags
        if text.strip().startswith('<v '):
            # Find the end of the voice tag
            match = re.match(r'^(<v [^>]+>)(.*)$', text)
            if match:
                voice_tag, content = match.groups()
                # Escape content but not the voice tag
                escaped_content = content
                for char, escape in self.escape_chars.items():
                    escaped_content = escaped_content.replace(char, escape)
                return voice_tag + escaped_content
        
        # Escape entire text
        escaped = text
        for char, escape in self.escape_chars.items():
            escaped = escaped.replace(char, escape)
        
        return escaped
    
    def _is_timestamp_line(self, line: str) -> bool:
        """Check if a line is a valid timestamp line."""
        pattern = r'^\d{1,}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{1,}:\d{2}:\d{2}\.\d{3}'
        return bool(re.match(pattern, line.strip()))
    
    def _normalize_line_endings(self, content: str) -> str:
        """Normalize line endings to LF only.
        
        Args:
            content: VTT content
            
        Returns:
            Content with normalized line endings
        """
        # Replace CRLF with LF
        content = content.replace('\r\n', '\n')
        # Remove any lone CR
        content = content.replace('\r', '\n')
        # Ensure no more than 2 consecutive newlines
        content = re.sub(r'\n{3,}', '\n\n', content)
        # Ensure file ends with single newline
        if not content.endswith('\n'):
            content += '\n'
        
        return content
    
    def _save_vtt_file(self, content: str, path: Path) -> None:
        """Save VTT content to file.
        
        Args:
            content: VTT content to save
            path: Path to save file
        """
        try:
            # Create parent directory if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file with UTF-8 encoding
            with open(path, 'w', encoding=self.encoding) as f:
                f.write(content)
            
            logger.info(f"VTT file saved to: {path}")
            
            # Mark checkpoint as completed if enabled
            if self.checkpoint_manager:
                self.checkpoint_manager.complete_stage('vtt_generation')
                self.checkpoint_manager.mark_completed(str(path))
            
        except Exception as e:
            logger.error(f"Failed to save VTT file: {e}")
            raise
    
    def create_metadata_from_episode(self, 
                                   episode_data: Dict[str, Any],
                                   speaker_mapping: Optional[Dict[str, str]] = None) -> VTTMetadata:
        """Create VTTMetadata from episode data.
        
        Args:
            episode_data: Episode information
            speaker_mapping: Optional speaker identification results
            
        Returns:
            VTTMetadata instance
        """
        # Extract guest names from speaker mapping if available
        guests = []
        host = None
        
        if speaker_mapping:
            for label, name in speaker_mapping.items():
                if 'Guest' in name and name not in guests:
                    # Extract just the name part
                    guest_name = name.split('(')[0].strip()
                    if guest_name and guest_name != 'Guest':
                        guests.append(guest_name)
                elif 'Host' in name:
                    host = name.split('(')[0].strip()
        
        # Fall back to author if no host found in speaker mapping
        if not host:
            host = episode_data.get('author')
        
        return VTTMetadata(
            podcast_name=episode_data.get('podcast_name', 'Unknown Podcast'),
            episode_title=episode_data.get('title', 'Unknown Episode'),
            publication_date=episode_data.get('published_date', 'Unknown'),
            duration=episode_data.get('duration'),
            host=host,
            guests=guests if guests else None,
            description=episode_data.get('description'),
            youtube_url=episode_data.get('youtube_url'),
            transcription_date=datetime.now().isoformat(),
            speakers=speaker_mapping
        )
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem compatibility.
        
        Args:
            filename: Raw filename
            
        Returns:
            Sanitized filename
        """
        # Remove leading/trailing dots and spaces first
        filename = filename.strip('. ')
        
        # Remove or replace invalid characters
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Replace forward/back slashes
        filename = filename.replace('/', '_').replace('\\', '_')
        
        # Replace spaces with underscores
        filename = filename.replace(' ', '_')
        
        # Limit length (leave room for .vtt extension)
        max_length = 200
        if len(filename) > max_length:
            filename = filename[:max_length]
        
        # Ensure not empty
        if not filename:
            filename = 'untitled'
        
        return filename
    
    def generate_output_path(self, 
                           episode_data: Dict[str, Any],
                           output_dir: Path) -> Path:
        """Generate output path for VTT file.
        
        Args:
            episode_data: Episode information
            output_dir: Base output directory
            
        Returns:
            Path for VTT file
        """
        # Create podcast subdirectory
        podcast_name = self.sanitize_filename(
            episode_data.get('podcast_name', 'Unknown_Podcast')
        )
        podcast_dir = output_dir / podcast_name
        
        # Generate filename
        date_str = episode_data.get('published_date', 'unknown')
        if date_str and date_str != 'unknown':
            try:
                # Try to parse and format date
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                date_str = date_obj.strftime('%Y-%m-%d')
            except:
                # Use as-is if parsing fails
                date_str = self.sanitize_filename(date_str)
        
        title = self.sanitize_filename(
            episode_data.get('title', 'untitled')
        )
        
        filename = f"{date_str}_{title}.vtt"
        
        return podcast_dir / filename