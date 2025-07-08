import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react'

const LayoutContext = createContext()

function usePanelState(panelName, defaultOpen = true) {
  const storageKey = `panel-${panelName}-open`
  const panelRef = useRef(null)
  
  const [isOpen, setIsOpen] = useState(() => {
    if (typeof window === 'undefined') return defaultOpen
    
    try {
      const stored = localStorage.getItem(storageKey)
      return stored !== null ? JSON.parse(stored) : defaultOpen
    } catch {
      return defaultOpen
    }
  })
  
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(isOpen))
    } catch (error) {
      console.warn('Failed to save panel state:', error)
    }
  }, [isOpen, storageKey])
  
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === storageKey && e.newValue !== null) {
        try {
          setIsOpen(JSON.parse(e.newValue))
        } catch {}
      }
    }
    
    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [storageKey])
  
  const toggle = useCallback(() => {
    setIsOpen(prev => !prev)
  }, [])
  
  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target) && isOpen) {
        setIsOpen(false)
      }
    }
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])
  
  return { isOpen, setIsOpen, toggle, panelRef }
}

export function LayoutProvider({ children }) {
  const menu = usePanelState('menu', false)
  const statements = usePanelState('statements', true)
  const analytics = usePanelState('analytics', false)
  const settings = usePanelState('settings', false)
  
  const resetLayout = useCallback(() => {
    menu.setIsOpen(false)
    statements.setIsOpen(true)
    analytics.setIsOpen(false)
    settings.setIsOpen(false)
  }, [menu, statements, analytics, settings])
  
  const value = useMemo(() => ({
    menu,
    statements,
    analytics,
    settings,
    resetLayout
  }), [menu, statements, analytics, settings, resetLayout])
  
  return (
    <LayoutContext.Provider value={value}>
      {children}
    </LayoutContext.Provider>
  )
}

export const useLayout = () => {
  const context = useContext(LayoutContext)
  if (!context) {
    throw new Error('useLayout must be used within LayoutProvider')
  }
  return context
}