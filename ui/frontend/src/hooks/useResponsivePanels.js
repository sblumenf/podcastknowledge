import { useState, useEffect } from 'react'

function useResponsivePanels() {
  const [dimensions, setDimensions] = useState({
    menuWidth: 180,
    statementsWidth: 340,
    isMobile: false,
    isTablet: false
  })
  
  useEffect(() => {
    const updateDimensions = () => {
      const width = window.innerWidth
      
      setDimensions({
        menuWidth: width < 768 ? width : 180,
        statementsWidth: width < 768 ? width : 
                        width < 1024 ? 280 : 340,
        isMobile: width < 768,
        isTablet: width >= 768 && width < 1024
      })
    }
    
    updateDimensions()
    window.addEventListener('resize', updateDimensions)
    
    return () => window.removeEventListener('resize', updateDimensions)
  }, [])
  
  return dimensions
}

export default useResponsivePanels