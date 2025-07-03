import { useParams } from 'react-router-dom'
import { useRef, useState, useEffect } from 'react'
import { PanelDivider } from './PanelDivider'
import { ChatPanel } from './ChatPanel'
import { EpisodePanel } from './EpisodePanel'
import { GraphPanel } from './GraphPanel'
import { Breadcrumbs } from './Breadcrumbs'
import { CollapseIcon } from './CollapseIcon'
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
  
  // Store widths before collapse to restore later
  const [preCollapseLeftWidth, setPreCollapseLeftWidth] = useState(25)
  const [preCollapseRightWidth, setPreCollapseRightWidth] = useState(25)
  
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
        setPreCollapseLeftWidth(state.preCollapseLeftWidth || state.leftWidth || 25)
        setPreCollapseRightWidth(state.preCollapseRightWidth || state.rightWidth || 25)
        setLeftCollapsed(state.leftCollapsed || false)
        setRightCollapsed(state.rightCollapsed || false)
      } catch {
        // Invalid saved state, use defaults
      }
    }
  }, [])
  
  // Save state to localStorage
  useEffect(() => {
    const state = {
      leftWidth,
      rightWidth,
      preCollapseLeftWidth,
      preCollapseRightWidth,
      leftCollapsed,
      rightCollapsed
    }
    localStorage.setItem('panelState', JSON.stringify(state))
  }, [leftWidth, rightWidth, preCollapseLeftWidth, preCollapseRightWidth, leftCollapsed, rightCollapsed])
  
  /**
   * Toggle collapse state for left panel
   */
  const toggleLeftCollapse = () => {
    if (leftCollapsed) {
      // Restore to previous width
      setLeftWidth(preCollapseLeftWidth)
    } else {
      // Store current width before collapsing
      setPreCollapseLeftWidth(leftWidth)
    }
    setLeftCollapsed(!leftCollapsed)
  }
  
  /**
   * Toggle collapse state for right panel
   */
  const toggleRightCollapse = () => {
    if (rightCollapsed) {
      // Restore to previous width
      setRightWidth(preCollapseRightWidth)
    } else {
      // Store current width before collapsing
      setPreCollapseRightWidth(rightWidth)
    }
    setRightCollapsed(!rightCollapsed)
  }
  
  /**
   * Handles resizing of the left panel
   * @param delta - Mouse movement delta in pixels
   */
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
  
  /**
   * Handles resizing of the right panel
   * @param delta - Mouse movement delta in pixels (negative when dragging left)
   */
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
  const collapsedSize = 48 // px - narrower to match NotebookLM
  
  // Calculate actual widths accounting for collapsed panels
  const getActualWidth = (baseWidth: number, isCollapsed: boolean) => {
    if (!containerRef.current) return baseWidth
    const containerWidth = containerRef.current.offsetWidth
    const collapsedPercent = (collapsedSize / containerWidth) * 100
    return isCollapsed ? collapsedPercent : baseWidth
  }
  
  const actualLeftWidth = getActualWidth(leftWidth, leftCollapsed)
  const actualRightWidth = getActualWidth(rightWidth, rightCollapsed)
  
  // Ensure middle panel takes remaining space properly
  const dividerSpace = 10 // 5px * 2 dividers
  const totalCollapsedSpace = (leftCollapsed ? collapsedSize : 0) + (rightCollapsed ? collapsedSize : 0)
  const availableSpace = 100 - (dividerSpace / (containerRef.current?.offsetWidth || 1000) * 100)
  
  const middleWidth = leftCollapsed && rightCollapsed 
    ? availableSpace - (totalCollapsedSpace / (containerRef.current?.offsetWidth || 1000) * 100)
    : 100 - actualLeftWidth - actualRightWidth
  
  // Build grid template with proper collapse sizing
  const leftColumnSize = leftCollapsed ? `${collapsedSize}px` : `${leftWidth}%`
  const rightColumnSize = rightCollapsed ? `${collapsedSize}px` : `${rightWidth}%`
  
  const gridTemplateColumns = `${leftColumnSize} 1px ${middleWidth}% 1px ${rightColumnSize}`
  
  return (
    <div className={styles.container} ref={containerRef}>
      <Breadcrumbs podcastId={id || ''} />
      <div className={styles.panelGrid} style={{ gridTemplateColumns }}>
        {/* Left Panel - Chat */}
        <section 
          className={`${styles.leftPanel} ${leftCollapsed ? styles.collapsed : ''}`} 
          ref={leftPanelRef}
        >
          <div className={styles.panelHeader}>
            {!leftCollapsed && <h2>Chat</h2>}
            <button 
              className={styles.collapseButton}
              onClick={toggleLeftCollapse}
              aria-label={leftCollapsed ? 'Expand chat panel' : 'Collapse chat panel'}
            >
              <CollapseIcon direction="left" />
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
            <GraphPanel podcastId={id || ''} />
          </div>
        </section>
        
        {/* Right Divider */}
        <PanelDivider onResize={handleRightResize} />
        
        {/* Right Panel - Episodes */}
        <section 
          className={`${styles.rightPanel} ${rightCollapsed ? styles.collapsed : ''}`} 
          ref={rightPanelRef}
        >
          <div className={styles.panelHeader}>
            {!rightCollapsed && <h2>Episodes</h2>}
            <button 
              className={styles.collapseButton}
              onClick={toggleRightCollapse}
              aria-label={rightCollapsed ? 'Expand episodes panel' : 'Collapse episodes panel'}
            >
              <CollapseIcon direction="right" />
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