import styles from './ErrorDisplay.module.css'

interface ErrorDisplayProps {
  error: string
  onRetry?: () => void
}

export function ErrorDisplay({ error, onRetry }: ErrorDisplayProps) {
  return (
    <div className={styles.container}>
      <div className={styles.content}>
        <svg 
          className={styles.icon}
          width="48" 
          height="48" 
          viewBox="0 0 24 24" 
          fill="none"
        >
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
          <path d="M12 8V12M12 16H12.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        <p className={styles.message}>{error}</p>
        {onRetry && (
          <button 
            className={styles.retryButton}
            onClick={onRetry}
          >
            Try again
          </button>
        )}
      </div>
    </div>
  )
}