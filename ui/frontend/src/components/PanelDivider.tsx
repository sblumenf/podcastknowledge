import { useEffect, useRef } from 'react'
import styles from './PanelDivider.module.css'

interface PanelDividerProps {
  onResize: (delta: number) => void
  orientation?: 'vertical' | 'horizontal'
}

export function PanelDivider({ onResize, orientation = 'vertical' }: PanelDividerProps) {
  const dividerRef = useRef<HTMLDivElement>(null)
  const isDragging = useRef(false)
  const startX = useRef(0)

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return
      
      const delta = e.clientX - startX.current
      startX.current = e.clientX
      onResize(delta)
    }

    const handleMouseUp = () => {
      isDragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    const handleMouseDown = (e: MouseEvent) => {
      isDragging.current = true
      startX.current = e.clientX
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      e.preventDefault()
    }

    const divider = dividerRef.current
    if (divider) {
      divider.addEventListener('mousedown', handleMouseDown)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      if (divider) {
        divider.removeEventListener('mousedown', handleMouseDown)
      }
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [onResize])

  return (
    <div 
      ref={dividerRef}
      className={`${styles.divider} ${styles[orientation]}`}
    >
      <div className={styles.handle} />
    </div>
  )
}