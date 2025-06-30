import { useState } from 'react'
import styles from './ViewControls.module.css'

export type ViewMode = 'grid' | 'list'
export type SortBy = 'recent' | 'title' | 'episodes'

interface ViewControlsProps {
  viewMode: ViewMode
  sortBy: SortBy
  onViewModeChange: (mode: ViewMode) => void
  onSortByChange: (sort: SortBy) => void
}

export function ViewControls({ viewMode, sortBy, onViewModeChange, onSortByChange }: ViewControlsProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false)

  return (
    <div className={styles.controls}>
      <button
        className={`${styles.viewButton} ${viewMode === 'list' ? styles.active : ''}`}
        onClick={() => onViewModeChange('list')}
        aria-label="List view"
        title="List view"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="5" y="4" width="1" height="1" fill="currentColor" />
          <rect x="7" y="4" width="8" height="1" fill="currentColor" />
          <rect x="5" y="9.5" width="1" height="1" fill="currentColor" />
          <rect x="7" y="9.5" width="8" height="1" fill="currentColor" />
          <rect x="5" y="15" width="1" height="1" fill="currentColor" />
          <rect x="7" y="15" width="8" height="1" fill="currentColor" />
        </svg>
      </button>
      
      <button
        className={`${styles.viewButton} ${viewMode === 'grid' ? styles.active : ''}`}
        onClick={() => onViewModeChange('grid')}
        aria-label="Grid view"
        title="Grid view"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="4" y="4" width="5" height="5" fill="currentColor" />
          <rect x="11" y="4" width="5" height="5" fill="currentColor" />
          <rect x="4" y="11" width="5" height="5" fill="currentColor" />
          <rect x="11" y="11" width="5" height="5" fill="currentColor" />
        </svg>
      </button>
      
      <button
        className={`${styles.viewButton} ${styles.grid3}`}
        onClick={() => onViewModeChange('grid')}
        aria-label="Grid view (3 columns)"
        title="Grid view (3 columns)"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="2" y="4" width="4" height="4" fill="currentColor" />
          <rect x="8" y="4" width="4" height="4" fill="currentColor" />
          <rect x="14" y="4" width="4" height="4" fill="currentColor" />
          <rect x="2" y="10" width="4" height="4" fill="currentColor" />
          <rect x="8" y="10" width="4" height="4" fill="currentColor" />
          <rect x="14" y="10" width="4" height="4" fill="currentColor" />
        </svg>
      </button>
      
      <div className={styles.dropdown}>
        <button
          className={styles.dropdownButton}
          onClick={() => setDropdownOpen(!dropdownOpen)}
        >
          {sortBy === 'recent' && 'Most recent'}
          {sortBy === 'title' && 'Title'}
          {sortBy === 'episodes' && 'Episode count'}
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className={styles.dropdownArrow}>
            <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
        
        {dropdownOpen && (
          <div className={styles.dropdownMenu}>
            <button
              className={`${styles.dropdownItem} ${sortBy === 'recent' ? styles.active : ''}`}
              onClick={() => {
                onSortByChange('recent')
                setDropdownOpen(false)
              }}
            >
              Most recent
            </button>
            <button
              className={`${styles.dropdownItem} ${sortBy === 'title' ? styles.active : ''}`}
              onClick={() => {
                onSortByChange('title')
                setDropdownOpen(false)
              }}
            >
              Title
            </button>
            <button
              className={`${styles.dropdownItem} ${sortBy === 'episodes' ? styles.active : ''}`}
              onClick={() => {
                onSortByChange('episodes')
                setDropdownOpen(false)
              }}
            >
              Episode count
            </button>
          </div>
        )}
      </div>
    </div>
  )
}