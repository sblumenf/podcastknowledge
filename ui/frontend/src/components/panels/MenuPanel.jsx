import React from 'react'
import { HiArrowLeft } from 'react-icons/hi'
import { useTheme } from '../../contexts/ThemeContext'

function MenuPanel({ podcast, onBack }) {
  const { theme, toggleTheme } = useTheme()
  
  return (
    <div className="h-full flex flex-col bg-surface">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
        >
          <HiArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </button>
      </div>
      
      {/* Podcast Info */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          {podcast?.name}
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {podcast?.episode_count} episodes
        </p>
      </div>
      
      {/* Menu Items */}
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          <li>
            <button className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Graph View</span>
            </button>
          </li>
          <li>
            <button className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Episodes</span>
            </button>
          </li>
          <li>
            <button className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Insights</span>
            </button>
          </li>
        </ul>
      </nav>
      
      {/* Footer */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={toggleTheme}
          className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Theme
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {theme === 'light' ? 'Light' : 'Dark'}
          </span>
        </button>
      </div>
    </div>
  )
}

export default MenuPanel