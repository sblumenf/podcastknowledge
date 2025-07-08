import React from 'react'
import { HiPlus, HiMinus, HiRefresh } from 'react-icons/hi'
import { SettingsIcon } from '../icons'
import { useLayout } from '../../contexts/LayoutContext'

function GraphControls() {
  const { settings } = useLayout()
  
  return (
    <div className="absolute top-4 right-4 flex flex-col gap-2">
      <button className="p-2 bg-white dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow">
        <HiPlus className="w-5 h-5" />
      </button>
      <button className="p-2 bg-white dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow">
        <HiMinus className="w-5 h-5" />
      </button>
      <button className="p-2 bg-white dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow">
        <HiRefresh className="w-5 h-5" />
      </button>
      <button 
        onClick={settings.toggle}
        className="p-2 bg-white dark:bg-gray-800 rounded-lg shadow-md hover:shadow-lg transition-shadow"
      >
        <SettingsIcon className="w-5 h-5" />
      </button>
    </div>
  )
}

export default GraphControls