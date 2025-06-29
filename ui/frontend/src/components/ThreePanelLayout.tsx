import { useParams } from 'react-router-dom'
import { useRef } from 'react'
import styles from './ThreePanelLayout.module.css'

export function ThreePanelLayout() {
  const { id } = useParams<{ id: string }>()
  
  // Refs for panel size management
  const containerRef = useRef<HTMLDivElement>(null)
  const leftPanelRef = useRef<HTMLDivElement>(null)
  const rightPanelRef = useRef<HTMLDivElement>(null)
  
  return (
    <div className={styles.container} ref={containerRef}>
      <div className={styles.panelGrid}>
        {/* Left Panel - Chat */}
        <section className={styles.leftPanel} ref={leftPanelRef}>
          <div className={styles.panelContent}>
            <h2>Chat</h2>
            <p>Podcast ID: {id}</p>
            <p>Chat panel - Phase 4 implementation pending</p>
          </div>
        </section>
        
        {/* Middle Panel - Knowledge Graph */}
        <section className={styles.middlePanel}>
          <div className={styles.panelContent}>
            <h2>Knowledge Graph</h2>
            <p>Graph placeholder - Phase 6 implementation pending</p>
          </div>
        </section>
        
        {/* Right Panel - Episodes */}
        <section className={styles.rightPanel} ref={rightPanelRef}>
          <div className={styles.panelContent}>
            <h2>Episodes</h2>
            <p>Episode list - Phase 5 implementation pending</p>
          </div>
        </section>
      </div>
    </div>
  )
}