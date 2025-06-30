import { memo, useState } from 'react'
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
  const [menuOpen, setMenuOpen] = useState(false)
  
  // Get podcast icon
  const icon = getPodcastIcon(podcast.id, podcast.category)
  
  // Format date (using current date as placeholder since we don't have actual dates)
  const formatDate = () => {
    const date = new Date()
    const month = date.toLocaleDateString('en-US', { month: 'short' })
    const day = date.getDate()
    const year = date.getFullYear()
    return `${day} ${month} ${year}`
  }
  
  // Get episode count (placeholder - would come from API)
  const episodeCount = Math.floor(Math.random() * 100) + 1
  
  const handleMenuClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setMenuOpen(!menuOpen)
  }
  
  const handleShare = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    // Share functionality would go here
    console.log('Share podcast:', podcast.name)
  }
  
  return (
    <Link 
      to={`/podcast/${podcast.id}`} 
      className={`${styles.card} ${viewMode === 'list' ? styles.listCard : ''}`}
    >
      {/* Three-dot menu */}
      <div className={styles.menuContainer}>
        <button 
          className={styles.menuButton}
          onClick={handleMenuClick}
          aria-label="More options"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="2" r="1.5" fill="currentColor" />
            <circle cx="8" cy="8" r="1.5" fill="currentColor" />
            <circle cx="8" cy="14" r="1.5" fill="currentColor" />
          </svg>
        </button>
        {menuOpen && (
          <div className={styles.menuDropdown}>
            <button className={styles.menuItem}>Rename</button>
            <button className={styles.menuItem}>Duplicate</button>
            <button className={styles.menuItem}>Delete</button>
          </div>
        )}
      </div>
      
      {/* Card content */}
      <div className={styles.cardContent}>
        <div className={styles.iconContainer}>
          <span className={styles.icon}>{icon}</span>
        </div>
        
        <h3 className={styles.title}>{podcast.name}</h3>
        
        <div className={styles.metadata}>
          <span className={styles.date}>{formatDate()}</span>
          <span className={styles.separator}>•</span>
          <span className={styles.episodes}>{episodeCount} episodes</span>
        </div>
      </div>
      
      {/* Share button */}
      <button 
        className={styles.shareButton}
        onClick={handleShare}
        aria-label="Share"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path 
            d="M3 9C3 7.89543 3.89543 7 5 7C6.10457 7 7 7.89543 7 9C7 10.1046 6.10457 11 5 11C3.89543 11 3 10.1046 3 9Z" 
            fill="currentColor"
          />
          <path 
            d="M11 4.5C11 3.39543 11.8954 2.5 13 2.5C14.1046 2.5 15 3.39543 15 4.5C15 5.60457 14.1046 6.5 13 6.5C11.8954 6.5 11 5.60457 11 4.5Z" 
            fill="currentColor"
          />
          <path 
            d="M11 13.5C11 12.3954 11.8954 11.5 13 11.5C14.1046 11.5 15 12.3954 15 13.5C15 14.6046 14.1046 15.5 13 15.5C11.8954 15.5 11 14.6046 11 13.5Z" 
            fill="currentColor"
          />
          <path 
            d="M6.5 8L11.5 5.5M6.5 10L11.5 12.5" 
            stroke="currentColor" 
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </Link>
  )
})