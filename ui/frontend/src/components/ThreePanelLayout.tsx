import { useParams } from 'react-router-dom'
import { useRef, useState, useEffect } from 'react'
import { PanelDivider } from './PanelDivider'
import { ChatPanel } from './ChatPanel'
import { EpisodePanel } from './EpisodePanel'
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
  
  // Collapse states
  const [leftCollapsed, setLeftCollapsed] = useState(false)
  const [rightCollapsed, setRightCollapsed] = useState(false)
  
  // Load saved state from localStorage
  useEffect(() => {
    const savedState = localStorage.getItem('panelState')
    if (savedState) {
      try {
        const state = JSON.parse(savedState)
        setLeftWidth(state.leftWidth || 25)
        setRightWidth(state.rightWidth || 25)
        setLeftCollapsed(state.leftCollapsed || false)
        setRightCollapsed(state.rightCollapsed || false)
      } catch (e) {
        // Invalid saved state, use defaults
      }
    }
  }, [])
  
  // Save state to localStorage
  useEffect(() => {
    const state = {
      leftWidth,
      rightWidth,
      leftCollapsed,
      rightCollapsed
    }
    localStorage.setItem('panelState', JSON.stringify(state))
  }, [leftWidth, rightWidth, leftCollapsed, rightCollapsed])
  
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
  
  // Calculate grid template with collapse states
  const collapsedSize = 64 // px
  const getColumnSize = (width: number, collapsed: boolean) => {
    return collapsed ? `${collapsedSize}px` : `${width}%`
  }
  
  const actualLeftWidth = leftCollapsed ? 0 : leftWidth
  const actualRightWidth = rightCollapsed ? 0 : rightWidth
  const middleWidth = 100 - actualLeftWidth - actualRightWidth
  
  const gridTemplateColumns = `${getColumnSize(leftWidth, leftCollapsed)} 4px ${middleWidth}% 4px ${getColumnSize(rightWidth, rightCollapsed)}`
  
  return (
    <div className={styles.container} ref={containerRef}>
      <div className={styles.panelGrid} style={{ gridTemplateColumns }}>
        {/* Left Panel - Chat */}
        <section className={`${styles.leftPanel} ${leftCollapsed ? styles.collapsed : ''}`} ref={leftPanelRef}>
          <div className={styles.panelHeader}>
            <h2>{leftCollapsed ? 'C' : 'Chat'}</h2>
            <button 
              className={styles.collapseButton}
              onClick={() => setLeftCollapsed(!leftCollapsed)}
              aria-label={leftCollapsed ? 'Expand chat panel' : 'Collapse chat panel'}
            >
              {leftCollapsed ? '→' : '←'}
            </button>
          </div>
          {!leftCollapsed && (
            <div className={styles.panelContent}>
              <ChatPanel podcastId={id || ''} />
            </div>
          )}
        </section>
        
        {/* Left Divider */}
        <PanelDivider onResize={handleLeftResize} />
        
        {/* Middle Panel - Knowledge Graph */}
        <section className={styles.middlePanel}>
          <div className={styles.panelHeader}>
            <h2>Knowledge Graph</h2>
          </div>
          <div className={styles.panelContent}>
            <p>Graph placeholder - Phase 6 implementation pending</p>
          </div>
        </section>
        
        {/* Right Divider */}
        <PanelDivider onResize={handleRightResize} />
        
        {/* Right Panel - Episodes */}
        <section className={`${styles.rightPanel} ${rightCollapsed ? styles.collapsed : ''}`} ref={rightPanelRef}>
          <div className={styles.panelHeader}>
            <h2>{rightCollapsed ? 'E' : 'Episodes'}</h2>
            <button 
              className={styles.collapseButton}
              onClick={() => setRightCollapsed(!rightCollapsed)}
              aria-label={rightCollapsed ? 'Expand episodes panel' : 'Collapse episodes panel'}
            >
              {rightCollapsed ? '←' : '→'}
            </button>
          </div>
          {!rightCollapsed && (
            <div className={styles.panelContent}>
              <EpisodePanel podcastId={id || ''} />
            </div>
          )}
        </section>
      </div>
    </div>
  )
}