import React from 'react'
import { useTheme } from '../contexts/ThemeContext'

function ThemedIcon({ lightIcon: LightIcon, darkIcon: DarkIcon, ...props }) {
  const { theme } = useTheme()
  
  // If no separate icons provided, use the same for both
  const Icon = theme === 'light' ? (LightIcon || DarkIcon) : (DarkIcon || LightIcon)
  
  return <Icon {...props} />
}

export default ThemedIcon