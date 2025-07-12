import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

function Dashboard() {
  const [podcasts, setPodcasts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sortBy, setSortBy] = useState('name')

  useEffect(() => {
    fetchPodcasts()
  }, [])

  const fetchPodcasts = async () => {
    try {
      const response = await fetch('/api/v1/podcasts')
      if (!response.ok) throw new Error('Failed to fetch podcasts')
      const data = await response.json()
      setPodcasts(data.podcasts || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const sortedPodcasts = [...podcasts].sort((a, b) => {
    switch (sortBy) {
      case 'name':
        return a.name.localeCompare(b.name)
      case 'episodes':
        return b.episode_count - a.episode_count
      case 'recent':
        return new Date(b.last_updated) - new Date(a.last_updated)
      default:
        return 0
    }
  })

  if (loading) return <div className="loading">Loading podcasts...</div>
  if (error) return <div className="error">Error: {error}</div>

  return (
    <div className="container">
      <div className="header">
        <h1>Podcast Knowledge</h1>
        <div className="sort-controls">
          <label>Sort by:</label>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="name">Name</option>
            <option value="episodes">Episode Count</option>
            <option value="recent">Last Updated</option>
          </select>
        </div>
      </div>

      <div className="dashboard">
        {sortedPodcasts.map((podcast) => (
          <Link 
            key={podcast.id} 
            to={`/podcast/${podcast.id}`}
            className="podcast-card"
          >
            <h3>{podcast.name}</h3>
            <div className="metadata">
              <span className="status-dot"></span>
              <span>{podcast.episode_count} episodes</span>
              <span>•</span>
              <span>{new Date(podcast.last_updated).toLocaleDateString()}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}

export default Dashboard