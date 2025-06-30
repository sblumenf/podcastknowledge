import { memo } from 'react'
import { Link } from 'react-router-dom'
import type { Podcast } from '../types'
import { getPodcastIcon } from '../utils/podcastIcons'
import styles from './PodcastCard.module.css'

interface PodcastCardProps {
  podcast: Podcast
  viewMode?: 'grid' | 'list'
}

export const PodcastCard = memo(function PodcastCard({ 
  podcast, 
  viewMode = 'grid' 
}: PodcastCardProps) {
  // Get podcast icon
  const icon = getPodcastIcon(podcast.id, podcast.category)
  
  return (
    <Link 
      to={`/podcast/${podcast.id}`} 
      className={`${styles.card} ${viewMode === 'list' ? styles.listCard : ''}`}
    >
      <div className={styles.cardContent}>
        <div className={styles.iconContainer}>
          <span className={styles.icon}>{icon}</span>
        </div>
        
        <div className={styles.info}>
          <h3 className={styles.title}>{podcast.name}</h3>
          <p className={styles.category}>{podcast.category}</p>
        </div>
      </div>
    </Link>
  )
})