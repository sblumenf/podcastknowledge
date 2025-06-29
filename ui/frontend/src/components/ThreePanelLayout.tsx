import { useParams } from 'react-router-dom'
import { useRef, useState } from 'react'
import { PanelDivider } from './PanelDivider'
import styles from './ThreePanelLayout.module.css'

export function ThreePanelLayout() {
  const { id } = useParams<{ id: string }>()
  
  // Refs for panel size management
  const containerRef = useRef<HTMLDivElement>(null)
  const leftPanelRef = useRef<HTMLDivElement>(null)
  const rightPanelRef = useRef<HTMLDivElement>(null)
  
  // Panel sizes in percentages
  const [leftWidth, setLeftWidth] = useState(25)
  const [rightWidth, setRightWidth] = useState(25)
  
  const handleLeftResize = (delta: number) => {
    const container = containerRef.current
    if (!container) return
    
    const containerWidth = container.offsetWidth
    const deltaPercent = (delta / containerWidth) * 100
    
    // Calculate new widths with minimum constraints
    const newLeftWidth = Math.max(200 / containerWidth * 100, Math.min(40, leftWidth + deltaPercent))
    
    setLeftWidth(newLeftWidth)
    // Adjust middle panel size (right panel stays the same)
  }
  
  const handleRightResize = (delta: number) => {
    const container = containerRef.current
    if (!container) return
    
    const containerWidth = container.offsetWidth
    const deltaPercent = (delta / containerWidth) * 100
    
    // Calculate new widths with minimum constraints
    const newRightWidth = Math.max(200 / containerWidth * 100, Math.min(40, rightWidth - deltaPercent))
    
    setRightWidth(newRightWidth)
    // Adjust middle panel size (left panel stays the same)
  }
  
  const middleWidth = 100 - leftWidth - rightWidth
  const gridTemplateColumns = `${leftWidth}% 4px ${middleWidth}% 4px ${rightWidth}%`
  
  return (
    <div className={styles.container} ref={containerRef}>
      <div className={styles.panelGrid} style={{ gridTemplateColumns }}>
        {/* Left Panel - Chat */}
        <section className={styles.leftPanel} ref={leftPanelRef}>
          <div className={styles.panelContent}>
            <h2>Chat</h2>
            <p>Podcast ID: {id}</p>
            <p>Chat panel - Phase 4 implementation pending</p>
          </div>
        </section>
        
        {/* Left Divider */}
        <PanelDivider onResize={handleLeftResize} />
        
        {/* Middle Panel - Knowledge Graph */}
        <section className={styles.middlePanel}>
          <div className={styles.panelContent}>
            <h2>Knowledge Graph</h2>
            <p>Graph placeholder - Phase 6 implementation pending</p>
          </div>
        </section>
        
        {/* Right Divider */}
        <PanelDivider onResize={handleRightResize} />
        
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