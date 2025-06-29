import styles from './GraphPanel.module.css'

export function GraphPanel() {
  return (
    <div className={styles.container}>
      <div className={styles.content}>
        <div className={styles.iconContainer}>
          <svg 
            className={styles.icon} 
            viewBox="0 0 24 24" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
            <circle cx="6" cy="6" r="2" stroke="currentColor" strokeWidth="2"/>
            <circle cx="18" cy="6" r="2" stroke="currentColor" strokeWidth="2"/>
            <circle cx="6" cy="18" r="2" stroke="currentColor" strokeWidth="2"/>
            <circle cx="18" cy="18" r="2" stroke="currentColor" strokeWidth="2"/>
            <path d="M12 9 L6 6" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M12 9 L18 6" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M12 15 L6 18" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M12 15 L18 18" stroke="currentColor" strokeWidth="1.5"/>
          </svg>
        </div>
        <h2 className={styles.title}>Knowledge Graph</h2>
        <p className={styles.comingSoon}>Coming Soon</p>
        <p className={styles.description}>
          Interactive visualization of podcast knowledge connections,
          topics, and relationships will appear here.
        </p>
      </div>
      <div className={styles.backgroundPattern}></div>
    </div>
  )
}