import { Link } from 'react-router-dom'
import type { Podcast } from '../types'
import styles from './PodcastCard.module.css'

interface PodcastCardProps {
  podcast: Podcast
}

export function PodcastCard({ podcast }: PodcastCardProps) {
  return (
    <Link to={`/podcast/${podcast.id}`} className={styles.card}>
      <div className={styles.cardContent}>
        <h2 className={styles.title}>{podcast.name}</h2>
        <p className={styles.host}>Hosted by {podcast.host}</p>
        <span className={styles.category}>{podcast.category}</span>
      </div>
    </Link>
  )
}