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