import { useEffect, useState, useCallback } from 'react'
import Graph from 'graphology'
import { SigmaContainer, useLoadGraph, useRegisterEvents, useSigma } from '@react-sigma/core'
import { LayoutForceAtlas2Control } from '@react-sigma/layout-forceatlas2'
import '@react-sigma/core/lib/style.css'
import { getKnowledgeGraph, getClusterMeaningfulUnits, type KnowledgeGraphData } from '../services/api'
import type { MeaningfulUnit } from '../types/meaningfulUnit'
import styles from './GraphPanel.module.css'

interface GraphPanelProps {
  podcastId: string
}

// Type for nodes with metadata
interface NodeData {
  label: string
  size: number
  color: string
  x: number
  y: number
  type?: 'cluster' | 'meaningfulUnit'
  clusterId?: string
}

// Component to handle graph events and spoke visualization
interface GraphEventsProps {
  podcastId: string
  selectedClusterId: string | null
  setSelectedClusterId: (id: string | null) => void
  spokeUnits: MeaningfulUnit[]
  setSpokeUnits: (units: MeaningfulUnit[]) => void
  spokeConfig: SpokeConfig
}

function GraphEvents({ 
  podcastId, 
  selectedClusterId, 
  setSelectedClusterId, 
  spokeUnits, 
  setSpokeUnits,
  spokeConfig 
}: GraphEventsProps) {
  const registerEvents = useRegisterEvents()
  const sigma = useSigma()
  const graph = sigma.getGraph()
  const [loadingSpokes, setLoadingSpokes] = useState(false)

  // Function to clear previous spokes
  const clearSpokes = useCallback(() => {
    // Remove all meaningful unit nodes
    graph.forEachNode((node, attributes) => {
      if (attributes.type === 'meaningfulUnit') {
        graph.dropNode(node)
      }
    })
    setSpokeUnits([])
  }, [graph, setSpokeUnits])

  // Function to handle cluster click
  const handleClusterClick = useCallback(async (nodeId: string) => {
    const nodeAttributes = graph.getNodeAttributes(nodeId) as NodeData
    
    // Only handle clicks on cluster nodes
    if (nodeAttributes.type !== 'cluster' && !nodeAttributes.type) {
      // If no type, assume it's a cluster (for backward compatibility)
      nodeAttributes.type = 'cluster'
    }
    
    if (nodeAttributes.type !== 'cluster') return

    // Toggle selection
    if (selectedClusterId === nodeId) {
      // Deselect and clear spokes
      setSelectedClusterId(null)
      clearSpokes()
    } else {
      // Select new cluster and fetch spokes
      setSelectedClusterId(nodeId)
      clearSpokes()
      
      if (spokeConfig.showSpokes) {
        setLoadingSpokes(true)
        try {
          const response = await getClusterMeaningfulUnits(podcastId, nodeId, spokeConfig.count)
          setSpokeUnits(response.meaningful_units)
          
          // Add spoke nodes to graph
          const clusterNode = graph.getNodeAttributes(nodeId) as NodeData
          const radius = 60 // Fixed radius for spokes
          const positions = calculateSpokePositions(
            clusterNode.x,
            clusterNode.y,
            radius,
            response.meaningful_units.length
          )
          
          // Add meaningful unit nodes and edges
          response.meaningful_units.forEach((unit, index) => {
            const unitNodeId = `unit-${unit.id}`
            const position = positions[index]
            
            // Add spoke node
            graph.addNode(unitNodeId, {
              label: unit.summary.substring(0, 30) + '...',
              size: 5,
              color: getSentimentColor(unit.sentiment),
              x: position.x,
              y: position.y,
              type: 'meaningfulUnit' as const,
              clusterId: nodeId,
              meaningfulUnit: unit
            })
            
            // Add edge from cluster to spoke
            graph.addEdge(nodeId, unitNodeId, {
              size: 0.5,
              color: 'rgba(150, 150, 150, 0.3)'
            })
          })
        } catch (error) {
          console.error('Failed to fetch meaningful units:', error)
        } finally {
          setLoadingSpokes(false)
        }
      }
    }
  }, [podcastId, selectedClusterId, setSelectedClusterId, spokeConfig, graph, clearSpokes, setSpokeUnits])

  useEffect(() => {
    // Register click event
    registerEvents({
      clickNode: (event) => {
        handleClusterClick(event.node)
      }
    })
  }, [registerEvents, handleClusterClick])
  
  // Clear spokes when showSpokes is toggled off
  useEffect(() => {
    if (!spokeConfig.showSpokes && selectedClusterId) {
      clearSpokes()
    }
  }, [spokeConfig.showSpokes, selectedClusterId, clearSpokes])

  return null
}

// Component to load graph data
interface LoadGraphProps {
  data: KnowledgeGraphData
  onGraphLoaded?: () => void
}

function LoadGraph({ data, onGraphLoaded }: LoadGraphProps) {
  const loadGraph = useLoadGraph()

  useEffect(() => {
    const graph = new Graph()
    
    // Add nodes (clusters)
    data.clusters.forEach(cluster => {
      const color = getNodeColor(cluster.connections)
      graph.addNode(cluster.id, {
        label: cluster.label,
        size: Math.sqrt(cluster.size) * 5, // Scale based on member count
        color,
        x: Math.random() * 100,
        y: Math.random() * 100,
        type: 'cluster' as const,
        centroid: cluster.centroid
      })
    })
    
    // Add edges with logarithmic scaling already applied from backend
    data.edges.forEach(edge => {
      graph.addEdge(edge.source, edge.target, {
        weight: edge.weight,
        size: 0.5 + edge.weight * 4.5 // Map normalized weight to 0.5-5px
      })
    })
    
    loadGraph(graph)
    onGraphLoaded?.()
  }, [data, loadGraph, onGraphLoaded])
  
  return null
}

// Get color based on interconnectedness
function getNodeColor(connections: number): string {
  if (connections > 10) return '#00FFFF' // Bright cyan - highly connected
  if (connections > 5) return '#FF00FF'  // Electric magenta - medium
  return '#0000FF' // Deep blue - isolated
}

// Get color based on sentiment polarity
function getSentimentColor(sentiment: { polarity: number }): string {
  const { polarity } = sentiment
  
  // Positive sentiment (polarity > 0.3)
  if (polarity > 0.3) return '#27ae60' // Green
  
  // Negative sentiment (polarity < -0.3)
  if (polarity < -0.3) return '#e74c3c' // Red
  
  // Neutral sentiment (-0.3 <= polarity <= 0.3)
  return '#95a5a6' // Gray
}

// Optional: Get color with intensity based on score
function getSentimentColorWithIntensity(sentiment: { polarity: number; score: number }): string {
  const baseColor = getSentimentColor(sentiment)
  const intensity = Math.abs(sentiment.score)
  
  // Apply opacity based on score intensity (0.5 to 1.0)
  const opacity = 0.5 + intensity * 0.5
  
  // Convert hex to rgba with opacity
  const r = parseInt(baseColor.slice(1, 3), 16)
  const g = parseInt(baseColor.slice(3, 5), 16)
  const b = parseInt(baseColor.slice(5, 7), 16)
  
  return `rgba(${r}, ${g}, ${b}, ${opacity})`
}

// Calculate spoke positions in a circle around cluster
function calculateSpokePositions(
  centerX: number,
  centerY: number,
  radius: number,
  count: number
): Array<{ x: number; y: number }> {
  const positions: Array<{ x: number; y: number }> = []
  
  for (let i = 0; i < count; i++) {
    const angle = (2 * Math.PI * i) / count
    const x = centerX + radius * Math.cos(angle)
    const y = centerY + radius * Math.sin(angle)
    positions.push({ x, y })
  }
  
  return positions
}

// Configuration for spoke visualization
interface SpokeConfig {
  count: number
  showSpokes: boolean
}

// Color legend component
function ColorLegend({ visible }: { visible: boolean }) {
  if (!visible) return null
  
  return (
    <div className={styles.colorLegend}>
      <h4>Sentiment</h4>
      <div className={styles.legendItem}>
        <div className={styles.legendColor} style={{ backgroundColor: '#27ae60' }} />
        <span>Positive</span>
      </div>
      <div className={styles.legendItem}>
        <div className={styles.legendColor} style={{ backgroundColor: '#95a5a6' }} />
        <span>Neutral</span>
      </div>
      <div className={styles.legendItem}>
        <div className={styles.legendColor} style={{ backgroundColor: '#e74c3c' }} />
        <span>Negative</span>
      </div>
    </div>
  )
}

export function GraphPanel({ podcastId }: GraphPanelProps) {
  const [graphData, setGraphData] = useState<KnowledgeGraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [connectionType, setConnectionType] = useState<string>('hybrid')
  
  // Spoke visualization state
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null)
  const [spokeUnits, setSpokeUnits] = useState<MeaningfulUnit[]>([])
  const [spokeConfig, setSpokeConfig] = useState<SpokeConfig>(() => {
    // Load saved preference from localStorage
    const savedCount = localStorage.getItem('spokeCount')
    return {
      count: savedCount ? parseInt(savedCount, 10) : 10,
      showSpokes: true
    }
  })
  
  // Handle spoke count change - refetch if cluster is selected
  const handleSpokeCountChange = useCallback((newCount: number) => {
    setSpokeConfig(prev => ({ ...prev, count: newCount }))
    localStorage.setItem('spokeCount', newCount.toString())
    
    // If a cluster is selected and count increased beyond cached amount, refetch
    if (selectedClusterId && newCount > spokeUnits.length) {
      // Force a re-click on the selected cluster to fetch new spokes
      setSelectedClusterId(null)
      setTimeout(() => setSelectedClusterId(selectedClusterId), 0)
    }
  }, [selectedClusterId, spokeUnits.length])
  
  useEffect(() => {
    let mounted = true
    
    async function fetchData() {
      try {
        setLoading(true)
        setError(null)
        const data = await getKnowledgeGraph(podcastId, connectionType)
        if (mounted) {
          setGraphData(data)
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to load knowledge graph')
        }
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }
    
    fetchData()
    
    return () => {
      mounted = false
    }
  }, [podcastId, connectionType])
  
  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading knowledge graph...</div>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>Error: {error}</div>
      </div>
    )
  }
  
  if (!graphData || graphData.clusters.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.empty}>No knowledge graph data available</div>
      </div>
    )
  }
  return (
    <div className={styles.container}>
      <div className={styles.controls}>
        <label>Connection Type: </label>
        <select 
          value={connectionType} 
          onChange={(e) => setConnectionType(e.target.value)}
          className={styles.connectionSelector}
        >
          <option value="episodes">Shared Episodes</option>
          <option value="temporal">Temporal Proximity</option>
          <option value="semantic">Semantic Similarity</option>
          <option value="hybrid">All Connections</option>
        </select>
        
        <div className={styles.spokeControls}>
          <label htmlFor="spokeCount">Spokes per cluster: {spokeConfig.count}</label>
          <input
            type="range"
            id="spokeCount"
            min="3"
            max="20"
            value={spokeConfig.count}
            onChange={(e) => handleSpokeCountChange(parseInt(e.target.value, 10))}
            className={styles.spokeSlider}
          />
          
          <label className={styles.toggleLabel}>
            <input
              type="checkbox"
              checked={spokeConfig.showSpokes}
              onChange={(e) => {
                const showSpokes = e.target.checked
                setSpokeConfig(prev => ({ ...prev, showSpokes }))
                
                // If toggling on with a selected cluster, refetch spokes
                if (showSpokes && selectedClusterId) {
                  // Force re-selection to show spokes
                  const currentSelection = selectedClusterId
                  setSelectedClusterId(null)
                  setTimeout(() => setSelectedClusterId(currentSelection), 0)
                }
              }}
              className={styles.spokeToggle}
            />
            <span>Show spokes</span>
          </label>
        </div>
      </div>
      <SigmaContainer 
        style={{ width: '100%', height: '100%' }}
        settings={{
          renderEdgeLabels: false,
          allowInvalidContainer: true,
          defaultNodeType: 'circle',
          defaultEdgeType: 'line',
          labelFont: 'Inter, system-ui, -apple-system, sans-serif',
          labelSize: 12,
          labelWeight: '500',
          labelColor: { color: '#FFFFFF' },
          stagePadding: 30,
          zoomDuration: 200,
          zoomingRatio: 1.2
        }}
      >
        <LoadGraph data={graphData} />
        <GraphEvents
          podcastId={podcastId}
          selectedClusterId={selectedClusterId}
          setSelectedClusterId={setSelectedClusterId}
          spokeUnits={spokeUnits}
          setSpokeUnits={setSpokeUnits}
          spokeConfig={spokeConfig}
        />
        <LayoutForceAtlas2Control 
          settings={{
            settings: {
              gravity: 1,
              scalingRatio: 10,
              barnesHutOptimize: true,
              strongGravityMode: false,
              outboundAttractionDistribution: false
            }
          }}
        />
      </SigmaContainer>
      <ColorLegend visible={spokeConfig.showSpokes && spokeUnits.length > 0} />
    </div>
  )
}