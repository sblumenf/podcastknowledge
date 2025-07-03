import { useState, useEffect, useRef, useCallback } from 'react'
import type { Episode } from '../types'
import { ErrorDisplay } from './ErrorDisplay'
import styles from './EpisodePanel.module.css'

interface EpisodePanelProps {
  podcastId: string
}

const ITEM_HEIGHT = 60 // Height of each episode item in pixels
const BUFFER_ITEMS = 5 // Extra items to render for smooth scrolling

export function EpisodePanel({ podcastId }: EpisodePanelProps) {
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [searchTerm, setSearchTerm] = useState('')
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('')
  
  const containerRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  
  const fetchEpisodes = useCallback(async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8002'}/api/podcasts/${podcastId}/episodes`)
      
      if (!response.ok) {
        throw new Error(`Unable to load episodes (${response.status})`)
      }
      
      const data = await response.json()
      setEpisodes(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load episodes')
    } finally {
      setLoading(false)
    }
  }, [podcastId])

  // Fetch episodes when podcast changes
  useEffect(() => {
    // Clear search when switching podcasts
    setSearchTerm('')
    setDebouncedSearchTerm('')
    
    fetchEpisodes()
  }, [fetchEpisodes])
  
  // Handle scroll for virtual scrolling with throttling
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const handleScroll = useCallback(() => {
    if (scrollTimeoutRef.current) return
    
    scrollTimeoutRef.current = setTimeout(() => {
      if (scrollRef.current) {
        setScrollTop(scrollRef.current.scrollTop)
      }
      scrollTimeoutRef.current = null
    }, 16) // ~60fps throttle
  }, [])
  
  // Cleanup scroll throttle on unmount
  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current)
      }
    }
  }, [])

  // Debounce search input
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }
    
    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm)
      // Reset scroll position when search changes
      if (scrollRef.current) {
        scrollRef.current.scrollTop = 0
        setScrollTop(0)
      }
    }, 300)
    
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
    }
  }, [searchTerm])
  
  // Filter episodes based on search term
  const filteredEpisodes = debouncedSearchTerm
    ? episodes.filter(episode => 
        episode.title.toLowerCase().includes(debouncedSearchTerm.toLowerCase())
      )
    : episodes
  
  /**
   * Virtual scrolling calculations
   * Only renders visible items plus a buffer for smooth scrolling
   */
  const containerHeight = containerRef.current?.clientHeight || 600
  const startIndex = Math.floor(scrollTop / ITEM_HEIGHT)
  const endIndex = Math.ceil((scrollTop + containerHeight) / ITEM_HEIGHT)
  
  // Add buffer items above and below visible area for smooth scrolling
  const visibleStartIndex = Math.max(0, startIndex - BUFFER_ITEMS)
  const visibleEndIndex = Math.min(filteredEpisodes.length, endIndex + BUFFER_ITEMS)
  const visibleEpisodes = filteredEpisodes.slice(visibleStartIndex, visibleEndIndex)
  
  // Total height for scroll container
  const totalHeight = filteredEpisodes.length * ITEM_HEIGHT
  
  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading episodes...</div>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className={styles.container}>
        <ErrorDisplay 
          error={error}
          onRetry={fetchEpisodes}
        />
      </div>
    )
  }
  
  if (episodes.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.empty}>No episodes found</div>
      </div>
    )
  }
  
  return (
    <div className={styles.container} ref={containerRef}>
      <div className={styles.searchContainer}>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Search episodes..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        {debouncedSearchTerm && (
          <span className={styles.resultCount}>
            {filteredEpisodes.length} of {episodes.length} episodes
          </span>
        )}
      </div>
      <div 
        className={styles.scrollContainer}
        ref={scrollRef}
        onScroll={handleScroll}
      >
        {filteredEpisodes.length === 0 ? (
          <div className={styles.noResults}>
            No episodes match "{debouncedSearchTerm}"
          </div>
        ) : (
          <div 
            className={styles.virtualSpacer}
            style={{ height: totalHeight }}
          >
            <div 
              className={styles.episodesList}
              style={{ transform: `translateY(${visibleStartIndex * ITEM_HEIGHT}px)` }}
            >
              {visibleEpisodes.map((episode) => {
                // Find actual index in original episodes array
                const originalIndex = episodes.findIndex(ep => ep.id === episode.id)
                return (
                  <div 
                    key={episode.id}
                    className={styles.episodeItem}
                    style={{ height: ITEM_HEIGHT }}
                  >
                    <span className={styles.episodeNumber}>
                      {originalIndex + 1}
                    </span>
                    <span className={styles.episodeTitle}>
                      {episode.title}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}