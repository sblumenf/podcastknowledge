// MeaningfulUnit data structures for hub-spoke visualization

export interface Sentiment {
  polarity: number
  score: number
  energy_level: number
  engagement_level: number
}

export interface MeaningfulUnit {
  id: string
  text: string
  summary: string
  embedding: number[]
  start_time: number
  end_time: number
  episode_id: string
  similarity: number
  sentiment: Sentiment
}

export interface MeaningfulUnitsResponse {
  cluster_id: string
  meaningful_units: MeaningfulUnit[]
  count: number
}