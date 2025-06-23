import { useState, useEffect } from 'react'
import { getWelcomeData } from '../services/api'
import './WelcomePage.module.css'

function WelcomePage() {
  const [podcastCount, setPodcastCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getWelcomeData()
        setPodcastCount(data.system_status.podcast_count)
        setError(null)
      } catch (err) {
        setError('Failed to connect to the server')
        console.error('Error fetching welcome data:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  return (
    <div className="welcome-page">
      <header className="welcome-header">
        <h1>Podcast Knowledge Explorer</h1>
        <p className="description">
          Explore knowledge graphs from your favorite podcasts
        </p>
        {loading && <p className="status">Loading...</p>}
        {error && <p className="error">{error}</p>}
        {!loading && !error && podcastCount !== null && (
          <p className="podcast-count">
            Currently tracking <strong>{podcastCount}</strong> podcast{podcastCount !== 1 ? 's' : ''}
          </p>
        )}
      </header>
      
      <section className="coming-soon">
        <h2>Coming Soon</h2>
        <ul className="feature-list">
          <li>Interactive knowledge graph visualization</li>
          <li>Search across all podcast content</li>
          <li>Topic exploration and discovery</li>
          <li>AI-powered insights and summaries</li>
        </ul>
      </section>
    </div>
  )
}

export default WelcomePage