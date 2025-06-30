import { useState, useEffect } from 'react'
import type { Podcast } from '../types'
import { PodcastCard } from './PodcastCard'
import { PodcastCardSkeleton } from './PodcastCardSkeleton'
import { ErrorDisplay } from './ErrorDisplay'
import { ViewControls, type ViewMode, type SortBy } from './ViewControls'
import { AddIcon } from './NavigationIcons'
import styles from './Dashboard.module.css'

export function Dashboard() {
  const [podcasts, setPodcasts] = useState<Podcast[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [sortBy, setSortBy] = useState<SortBy>('recent')

  const fetchPodcasts = () => {
    setLoading(true)
    setError(null)
    
    // Fetch podcasts from API
    // Source of truth: seeding_pipeline/config/podcasts.yaml
    fetch('http://localhost:8002/api/podcasts')
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
  
  // Sort podcasts based on selected option
  const sortedPodcasts = [...podcasts].sort((a, b) => {
    switch (sortBy) {
      case 'title':
        return a.name.localeCompare(b.name)
      case 'episodes':
        // For now, we don't have episode count, so we'll use name
        return a.name.localeCompare(b.name)
      case 'recent':
      default:
        // For now, sort by name (would use date if available)
        return a.name.localeCompare(b.name)
    }
  })

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
        <h1 className={styles.title}>Welcome to Podcast Knowledge</h1>
        <div className={styles.toolbar}>
          <button className={styles.createButton}>
            <AddIcon />
            <span>Create new</span>
          </button>
          <ViewControls
            viewMode={viewMode}
            sortBy={sortBy}
            onViewModeChange={setViewMode}
            onSortByChange={setSortBy}
          />
        </div>
      </header>
      
      <main className={styles.main}>
        <div className={`${styles.grid} ${viewMode === 'list' ? styles.listView : ''}`}>
          {showSkeletons ? (
            // Show 8 skeleton cards while loading
            Array.from({ length: 8 }).map((_, index) => (
              <PodcastCardSkeleton key={`skeleton-${index}`} />
            ))
          ) : (
            sortedPodcasts.map(podcast => (
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