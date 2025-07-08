import React, { createContext, useContext, useState, useEffect } from 'react'

const ThemeContext = createContext()

const THEME_STORAGE_KEY = 'podcast-theme'
const THEME_CHOSEN_KEY = 'podcast-theme-chosen'

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState('light')
  const [isLoading, setIsLoading] = useState(true)
  
  useEffect(() => {
    const initTheme = () => {
      const hasChosen = localStorage.getItem(THEME_CHOSEN_KEY) === 'true'
      const storedTheme = localStorage.getItem(THEME_STORAGE_KEY)
      
      if (hasChosen && storedTheme) {
        return storedTheme
      }
      
      if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
        return 'dark'
      }
      
      return 'light'
    }
    
    const initialTheme = initTheme()
    setThemeState(initialTheme)
    applyTheme(initialTheme)
    setIsLoading(false)
  }, [])
  
  const applyTheme = (newTheme) => {
    const root = document.documentElement
    
    root.classList.remove('light', 'dark')
    root.classList.add(newTheme)
    root.setAttribute('data-theme', newTheme)
    
    const metaThemeColor = document.querySelector('meta[name="theme-color"]')
    if (metaThemeColor) {
      metaThemeColor.content = newTheme === 'dark' ? '#000000' : '#f0ecec'
    }
  }
  
  const setTheme = (newTheme) => {
    setThemeState(newTheme)
    applyTheme(newTheme)
    
    localStorage.setItem(THEME_CHOSEN_KEY, 'true')
    localStorage.setItem(THEME_STORAGE_KEY, newTheme)
    
    window.dispatchEvent(new StorageEvent('storage', {
      key: THEME_STORAGE_KEY,
      newValue: newTheme,
      url: window.location.href
    }))
  }
  
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === THEME_STORAGE_KEY && e.newValue) {
        setThemeState(e.newValue)
        applyTheme(e.newValue)
      }
    }
    
    window.addEventListener('storage', handleStorageChange)
    return () => window.removeEventListener('storage', handleStorageChange)
  }, [])
  
  const value = {
    theme,
    setTheme,
    toggleTheme: () => setTheme(theme === 'light' ? 'dark' : 'light'),
    isLoading
  }
  
  return (
    <ThemeContext.Provider value={value}>
      {!isLoading && children}
    </ThemeContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}