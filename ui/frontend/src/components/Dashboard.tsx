import { useState, useEffect } from 'react'
import type { Podcast } from '../types'
import { PodcastCard } from './PodcastCard'
import { PodcastCardSkeleton } from './PodcastCardSkeleton'
import { ErrorDisplay } from './ErrorDisplay'
import { ViewToggle, type ViewMode } from './ViewToggle'
import styles from './Dashboard.module.css'

export function Dashboard() {
  const [podcasts, setPodcasts] = useState<Podcast[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')

  const fetchPodcasts = () => {
    setLoading(true)
    setError(null)
    
    // Fetch podcasts from API
    // Source of truth: seeding_pipeline/config/podcasts.yaml
    fetch('http://localhost:8001/api/podcasts')
      .then(response => {
        if (!response.ok) {
          throw new Error(`Unable to load podcasts (${response.status})`)
        }
        return response.json()
      })
      .then(data => {
        setPodcasts(data)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message || 'Failed to load podcasts')
        setLoading(false)
      })
  }

  useEffect(() => {
    fetchPodcasts()
  }, [])

  const showSkeletons = loading || podcasts.length === 0

  if (error) {
    return (
      <div className={styles.container}>
        <ErrorDisplay 
          error={error}
          onRetry={fetchPodcasts}
        />
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1 className={styles.title}>Podcast Knowledge</h1>
        <p className={styles.subtitle}>Select a podcast to explore</p>
        <div className={styles.toolbar}>
          <ViewToggle
            viewMode={viewMode}
            onViewModeChange={setViewMode}
          />
        </div>
      </header>
      
      <main className={styles.main}>
        <div className={`${styles.grid} ${viewMode === 'list' ? styles.listView : ''}`}>
          {showSkeletons ? (
            // Show 6 skeleton cards while loading
            Array.from({ length: 6 }).map((_, index) => (
              <PodcastCardSkeleton key={`skeleton-${index}`} />
            ))
          ) : (
            podcasts.map(podcast => (
              <PodcastCard 
                key={podcast.id} 
                podcast={podcast}
                viewMode={viewMode}
              />
            ))
          )}
        </div>
      </main>
    </div>
  )
}