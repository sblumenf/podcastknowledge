import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import type { Podcast } from '../types'
import styles from './Breadcrumbs.module.css'

interface BreadcrumbsProps {
  podcastId: string
}

export function Breadcrumbs({ podcastId }: BreadcrumbsProps) {
  const [podcastName, setPodcastName] = useState<string>('')
  
  useEffect(() => {
    // Fetch podcast info to get the name
    const fetchPodcastInfo = async () => {
      try {
        const response = await fetch('http://localhost:8001/api/podcasts')
        if (response.ok) {
          const podcasts: Podcast[] = await response.json()
          const currentPodcast = podcasts.find(p => p.id === podcastId)
          if (currentPodcast) {
            setPodcastName(currentPodcast.name)
          }
        }
      } catch (error) {
        // Silent fail - breadcrumbs are not critical
        console.error('Failed to fetch podcast info:', error)
      }
    }
    
    fetchPodcastInfo()
  }, [podcastId])
  
  return (
    <nav className={styles.breadcrumbs}>
      <Link to="/" className={styles.link}>
        Dashboard
      </Link>
      <span className={styles.separator}>›</span>
      <span className={styles.current}>
        {podcastName || 'Loading...'}
      </span>
    </nav>
  )
}