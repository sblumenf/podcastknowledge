import React from 'react'
import { useParams, Link } from 'react-router-dom'

function PodcastView() {
  const { podcastId } = useParams()

  return (
    <div className="container">
      <Link to="/" style={{ color: '#a0a0a0', textDecoration: 'none', marginBottom: '1rem', display: 'inline-block' }}>
        ← Back to Dashboard
      </Link>
      <h1>Podcast: {podcastId}</h1>
      <p style={{ marginTop: '2rem', color: '#a0a0a0' }}>
        Graph visualization for podcast "{podcastId}" will be displayed here.
      </p>
    </div>
  )
}

export default PodcastView