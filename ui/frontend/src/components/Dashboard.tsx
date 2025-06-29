import { useState, useEffect } from 'react'
import type { Podcast } from '../types'
import { PodcastCard } from './PodcastCard'
import styles from './Dashboard.module.css'

export function Dashboard() {
  const [podcasts, setPodcasts] = useState<Podcast[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Fetch podcasts from API
    // Source of truth: seeding_pipeline/config/podcasts.yaml
    fetch('http://localhost:8000/api/podcasts')
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        return response.json()
      })
      .then(data => {
        setPodcasts(data)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading podcasts...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>Error loading podcasts: {error}</div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Podcast Knowledge Discovery</h1>
        <p className={styles.subtitle}>Select a podcast to explore</p>
      </header>
      
      <main className={styles.main}>
        <div className={styles.grid}>
          {podcasts.map(podcast => (
            <PodcastCard key={podcast.id} podcast={podcast} />
          ))}
        </div>
      </main>
    </div>
  )
}