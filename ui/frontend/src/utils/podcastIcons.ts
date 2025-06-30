// Map podcast categories to emojis/icons
export const categoryIcons: Record<string, string> = {
  'Self-Improvement': '🎯',
  'Business': '💼',
  'Technology': '🚀',
  'Education': '📚',
  'Entertainment': '🎬',
  'News': '📰',
  'Sports': '⚽',
  'Health': '💚',
  'Science': '🔬',
  'Comedy': '😄',
  'Music': '🎵',
  'Politics': '🏛️'
}

// Specific podcast overrides (if needed)
export const podcastIcons: Record<string, string> = {
  'mel_robbins_podcast': '💪',
  'my_first_million': '💰'
}

export function getPodcastIcon(podcastId: string, category: string): string {
  // Check for specific podcast icon first
  if (podcastIcons[podcastId]) {
    return podcastIcons[podcastId]
  }
  
  // Fall back to category icon
  if (categoryIcons[category]) {
    return categoryIcons[category]
  }
  
  // Default icon
  return '📻'
}