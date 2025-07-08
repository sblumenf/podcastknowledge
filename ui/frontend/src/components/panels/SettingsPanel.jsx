import React from 'react'
import { HiX } from 'react-icons/hi'

function SettingsPanel({ onClose }) {
  return (
    <div className="h-full flex flex-col bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Settings</h2>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
        >
          <HiX className="w-5 h-5" />
        </button>
      </div>
      
      {/* Settings content */}
      <div className="flex-1 overflow-y-auto p-4">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Settings controls will be implemented in Session 07
        </p>
      </div>
    </div>
  )
}

export default SettingsPanel