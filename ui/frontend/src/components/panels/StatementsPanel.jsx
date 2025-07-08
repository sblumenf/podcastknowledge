import React, { useState, useEffect } from 'react'
import { useLayout } from '../../contexts/LayoutContext'

function StatementsPanel({ selectedNode }) {
  const { statements } = useLayout()
  const [activeTab, setActiveTab] = useState('insights')
  const [nodeData, setNodeData] = useState(null)
  
  useEffect(() => {
    if (selectedNode) {
      // In a real implementation, this would fetch node details from the API
      setNodeData({
        insights: [
          { id: 1, text: 'Key insight about this topic...', importance: 0.9 },
          { id: 2, text: 'Another important observation...', importance: 0.8 }
        ],
        quotes: [
          { id: 1, text: 'A memorable quote from the podcast...', speaker: 'Mel Robbins', importance_score: 0.85 },
          { id: 2, text: 'Another significant statement...', speaker: 'Guest', importance_score: 0.8 }
        ],
        context: {
          summary: 'This segment discusses...',
          themes: ['Leadership', 'Personal Growth'],
          duration: '5:32'
        }
      })
    }
  }, [selectedNode])
  
  const tabs = [
    { id: 'insights', label: 'Insights' },
    { id: 'quotes', label: 'Quotes' },
    { id: 'context', label: 'Context' }
  ]
  
  return (
    <div className="h-full flex flex-col bg-surface">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          {selectedNode ? selectedNode.label : 'Statements'}
        </h2>
        <button
          onClick={statements.toggle}
          className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      
      {selectedNode ? (
        <>
          {/* Tabs */}
          <div className="flex border-b border-gray-200 dark:border-gray-700">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'text-primary border-b-2 border-primary'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          
          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {activeTab === 'insights' && nodeData?.insights && (
              <div className="space-y-4">
                {nodeData.insights.map(insight => (
                  <div key={insight.id} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <p className="text-sm text-gray-700 dark:text-gray-300">{insight.text}</p>
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Importance: {(insight.importance * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {activeTab === 'quotes' && nodeData?.quotes && (
              <div className="space-y-4">
                {nodeData.quotes.map(quote => (
                  <div key={quote.id} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <p className="text-sm text-gray-700 dark:text-gray-300 italic">"{quote.text}"</p>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-xs text-gray-500 dark:text-gray-400">— {quote.speaker}</span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Score: {(quote.importance_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {activeTab === 'context' && nodeData?.context && (
              <div className="space-y-4">
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">Summary</h3>
                  <p className="text-sm text-gray-700 dark:text-gray-300">{nodeData.context.summary}</p>
                </div>
                
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">Themes</h3>
                  <div className="flex flex-wrap gap-2">
                    {nodeData.context.themes.map((theme, index) => (
                      <span
                        key={index}
                        className="px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded"
                      >
                        {theme}
                      </span>
                    ))}
                  </div>
                </div>
                
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-2">Duration</h3>
                  <p className="text-sm text-gray-700 dark:text-gray-300">{nodeData.context.duration}</p>
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
            Select a node in the graph to view its details
          </p>
        </div>
      )}
    </div>
  )
}

export default StatementsPanel