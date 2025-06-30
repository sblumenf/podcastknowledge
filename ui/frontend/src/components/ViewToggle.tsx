import styles from './ViewToggle.module.css'

export type ViewMode = 'grid' | 'list'

interface ViewToggleProps {
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
}

export function ViewToggle({ viewMode, onViewModeChange }: ViewToggleProps) {
  return (
    <div className={styles.toggle}>
      <button
        className={`${styles.button} ${viewMode === 'grid' ? styles.active : ''}`}
        onClick={() => onViewModeChange('grid')}
        aria-label="Grid view"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <rect x="2" y="2" width="6" height="6" fill="currentColor" />
          <rect x="10" y="2" width="6" height="6" fill="currentColor" />
          <rect x="2" y="10" width="6" height="6" fill="currentColor" />
          <rect x="10" y="10" width="6" height="6" fill="currentColor" />
        </svg>
      </button>
      
      <button
        className={`${styles.button} ${viewMode === 'list' ? styles.active : ''}`}
        onClick={() => onViewModeChange('list')}
        aria-label="List view"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <rect x="3" y="3" width="12" height="2" fill="currentColor" />
          <rect x="3" y="8" width="12" height="2" fill="currentColor" />
          <rect x="3" y="13" width="12" height="2" fill="currentColor" />
        </svg>
      </button>
    </div>
  )
}