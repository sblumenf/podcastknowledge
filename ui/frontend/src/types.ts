// Podcast interface matching /api/podcasts response
export interface Podcast {
  id: string
  name: string
  host: string
  category: string
  description: string
  tags: string[]
  enabled: boolean
  database_port: string | number
  database_name: string
}

// Episode interface for Neo4j episode data
export interface Episode {
  id: string
  title: string
  // Additional fields can be added as Neo4j schema is clarified
}

// ChatMessage interface matching /api/chat/{podcast_id} response
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

// PanelState interface for resize/collapse states
export interface PanelState {
  leftPanelWidth: number
  rightPanelWidth: number
  leftPanelCollapsed: boolean
  rightPanelCollapsed: boolean
}