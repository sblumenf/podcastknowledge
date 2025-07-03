import { useEffect, useState } from 'react'
import Graph from 'graphology'
import { SigmaContainer, useLoadGraph } from '@react-sigma/core'
import { LayoutForceAtlas2Control } from '@react-sigma/layout-forceatlas2'
import '@react-sigma/core/lib/style.css'
import { getKnowledgeGraph, type KnowledgeGraphData } from '../services/api'
import styles from './GraphPanel.module.css'

interface GraphPanelProps {
  podcastId: string
}

// Component to load graph data
function LoadGraph({ data }: { data: KnowledgeGraphData }) {
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
        y: Math.random() * 100
      })
    })
    
    // Add edges
    data.edges.forEach(edge => {
      graph.addEdge(edge.source, edge.target, {
        weight: edge.weight,
        size: Math.log(edge.weight + 1) // Logarithmic scale for edge thickness
      })
    })
    
    loadGraph(graph)
  }, [data, loadGraph])
  
  return null
}

// Get color based on interconnectedness
function getNodeColor(connections: number): string {
  if (connections > 10) return '#00FFFF' // Bright cyan - highly connected
  if (connections > 5) return '#FF00FF'  // Electric magenta - medium
  return '#0000FF' // Deep blue - isolated
}

export function GraphPanel({ podcastId }: GraphPanelProps) {
  const [graphData, setGraphData] = useState<KnowledgeGraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [connectionType, setConnectionType] = useState<string>('hybrid')
  
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
    </div>
  )
}