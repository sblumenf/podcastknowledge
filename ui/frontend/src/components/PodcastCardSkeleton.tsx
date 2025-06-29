import styles from './PodcastCardSkeleton.module.css'

export function PodcastCardSkeleton() {
  return (
    <div className={styles.card}>
      <div className={styles.cardContent}>
        <div className={styles.title} />
        <div className={styles.host} />
        <div className={styles.category} />
      </div>
    </div>
  )
}