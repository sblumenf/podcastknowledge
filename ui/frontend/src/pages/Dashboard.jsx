import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { HiPlus, HiDotsVertical } from 'react-icons/hi'
import { SettingsIcon, AppsIcon, CheckIcon, GridIcon, ListIcon, UserIcon, PodcastIcon } from '../components/icons'

const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric', 
    year: 'numeric' 
  })
}

function Dashboard() {
  const [podcasts, setPodcasts] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  
  useEffect(() => {
    fetchPodcasts()
  }, [])
  
  const fetchPodcasts = async () => {
    try {
      const response = await fetch('/api/v1/podcasts')
      const data = await response.json()
      setPodcasts(data.podcasts)
    } catch (error) {
      console.error('Failed to fetch podcasts:', error)
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="min-h-screen bg-[#1a1a1a] text-gray-200">
      {/* Header */}
      <header className="border-b border-gray-800">
        <div className="px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-light text-white">
              Podcast Knowledge
            </h1>
          </div>
          
          <div className="flex items-center gap-4">
            <button className="p-2 hover:bg-gray-800 rounded-lg transition-colors">
              <SettingsIcon className="w-5 h-5" />
            </button>
            <button className="p-2 hover:bg-gray-800 rounded-lg transition-colors">
              <AppsIcon className="w-5 h-5" />
            </button>
            <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
              <span className="text-sm font-medium">S</span>
            </div>
          </div>
        </div>
      </header>
      
      {/* Main content */}
      <main className="px-6 py-8">
        {/* Welcome section */}
        <div className="mb-12 text-center">
          <h2 className="text-5xl font-light text-white mb-8">
            Welcome to Podcast Knowledge
          </h2>
          
          {/* Create new button */}
          <button className="inline-flex items-center gap-2 px-4 py-2 bg-white text-gray-900 rounded-full hover:bg-gray-100 transition-colors">
            <HiPlus className="w-4 h-4" />
            <span>Create new</span>
          </button>
        </div>
        
        {/* View controls */}
        <div className="flex items-center justify-end gap-4 mb-6">
          <button className="p-2 hover:bg-gray-800 rounded">
            <CheckIcon className="w-5 h-5" />
          </button>
          <button className="p-2 hover:bg-gray-800 rounded">
            <GridIcon className="w-5 h-5" />
          </button>
          <button className="p-2 hover:bg-gray-800 rounded">
            <ListIcon className="w-5 h-5" />
          </button>
          <select className="bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm">
            <option>Most recent</option>
            <option>Alphabetical</option>
            <option>Most episodes</option>
          </select>
        </div>
        
        {/* Podcast grid */}
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {podcasts.map((podcast) => (
              <PodcastCard
                key={podcast.id}
                podcast={podcast}
                onClick={() => navigate(`/podcast/${podcast.id}`)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

function PodcastCard({ podcast, onClick }) {
  const [menuOpen, setMenuOpen] = useState(false)
  
  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
      className="group cursor-pointer"
      onClick={onClick}
    >
      <div className="bg-gray-800/50 rounded-lg p-6 h-full flex flex-col border border-gray-700/50 hover:border-gray-600 transition-colors">
        {/* Icon section */}
        <div className="mb-4 flex items-start justify-between">
          <div className={`w-16 h-16 rounded-lg bg-gradient-to-br ${podcast.theme_color} flex items-center justify-center`}>
            <PodcastIcon className="w-8 h-8 text-white" />
          </div>
          
          {/* Three dots menu */}
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation()
                setMenuOpen(!menuOpen)
              }}
              className="p-1 opacity-0 group-hover:opacity-100 hover:bg-gray-700 rounded transition-all"
            >
              <HiDotsVertical className="w-5 h-5" />
            </button>
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1">
          <h3 className="text-lg font-medium text-white mb-2 line-clamp-2">
            {podcast.name}
          </h3>
          
          <div className="flex items-center gap-3 text-sm text-gray-400">
            <span>{formatDate(podcast.last_updated)}</span>
            <span>•</span>
            <span>{podcast.episode_count} episodes</span>
          </div>
        </div>
        
        {/* Footer with host info */}
        <div className="mt-4 pt-4 border-t border-gray-700/50 flex items-center gap-2">
          <UserIcon className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-400">{podcast.host}</span>
        </div>
      </div>
    </motion.div>
  )
}

export default Dashboard