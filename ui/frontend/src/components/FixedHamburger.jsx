import React from 'react'
import { useLayout } from '../contexts/LayoutContext'

function FixedHamburger() {
  const { menu } = useLayout()
  
  return (
    <button
      onClick={menu.toggle}
      className="fixed top-4 left-4 z-30 w-12 h-12 flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
    >
      <div className="relative w-6 h-5">
        <span className={`absolute left-0 w-full h-0.5 bg-gray-700 dark:bg-gray-300 transition-all duration-200 ${menu.isOpen ? 'top-1/2 -translate-y-1/2 rotate-45' : 'top-0'}`} />
        <span className={`absolute left-0 top-1/2 -translate-y-1/2 w-full h-0.5 bg-gray-700 dark:bg-gray-300 transition-all duration-200 ${menu.isOpen ? 'opacity-0 scale-x-0' : 'opacity-100'}`} />
        <span className={`absolute left-0 w-full h-0.5 bg-gray-700 dark:bg-gray-300 transition-all duration-200 ${menu.isOpen ? 'bottom-1/2 translate-y-1/2 -rotate-45' : 'bottom-0'}`} />
      </div>
    </button>
  )
}

export default FixedHamburger