/**
 * API service for communicating with the backend
 */

// Get API URL from environment variable
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

// Types for API responses
interface WelcomeData {
  message: string
  system_status: {
    podcast_count: number
    status: string
    timestamp: string
  }
  description: string
}

interface RAGStatus {
  status: string
  uri?: string
  database?: string
  node_count?: number
  graphrag_ready: boolean
  error?: string
}

interface RAGSearchRequest {
  query: string
  top_k?: number
}

interface RAGSearchResult {
  content: string
  metadata?: Record<string, unknown>
  score?: number
}

interface RAGSearchResponse {
  query: string
  top_k: number
  results: RAGSearchResult[]
  message?: string
  error?: string
  details?: unknown
}

// Generic error handler
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.text()
    throw new Error(`API Error: ${response.status} - ${error}`)
  }
  return response.json()
}

// API functions
export async function getWelcomeData(): Promise<WelcomeData> {
  try {
    const response = await fetch(`${API_URL}/api/welcome`)
    return handleResponse<WelcomeData>(response)
  } catch (error) {
    console.error('Failed to fetch welcome data:', error)
    throw error
  }
}

// RAG API functions
export async function getRAGStatus(): Promise<RAGStatus> {
  try {
    const response = await fetch(`${API_URL}/api/rag/status`)
    return handleResponse<RAGStatus>(response)
  } catch (error) {
    console.error('Failed to fetch RAG status:', error)
    throw error
  }
}

export async function searchKnowledge(request: RAGSearchRequest): Promise<RAGSearchResponse> {
  try {
    const response = await fetch(`${API_URL}/api/rag/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request)
    })
    return handleResponse<RAGSearchResponse>(response)
  } catch (error) {
    console.error('Failed to search knowledge:', error)
    throw error
  }
}