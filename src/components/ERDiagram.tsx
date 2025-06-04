'use client'

import { useCallback, useMemo, useRef, useImperativeHandle, forwardRef, useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  MiniMap,
  Background,
  Handle,
  Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import styles from './ERDiagram.module.css'
import { Database, Key } from 'lucide-react'
import { DatabaseSchema, Table as TableType } from '../types/Table'

// Memoized TableNode component
const TableNode = ({ data }: { data: { table: TableType } }) => {
  const { table } = data

  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg shadow-lg min-w-[250px]">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-4 py-2 rounded-t-lg">
        <div className="flex items-center text-white font-bold">
          <Database className="w-4 h-4 mr-2" />
          {table.name}
        </div>
      </div>
      
      <div className="p-3 space-y-1">
        {table.columns.map((column, index) => (
          <div key={index} className="flex items-center justify-between text-sm py-1">
            <div className="flex items-center">
              {column.primaryKey && (
                <Key className="w-3 h-3 text-yellow-400 mr-2" />
              )}
              <span className={`${column.primaryKey ? 'text-yellow-400 font-semibold' : 'text-slate-200'}`}>
                {column.name}
              </span>
              <span className="text-slate-400 ml-2 text-xs">
                {column.type}
              </span>
            </div>
            
            <div className="flex space-x-1">
              {column.primaryKey && (
                <span className="px-1 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">PK</span>
              )}
              {column.foreignKey && (
                <span className="px-1 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs">FK</span>
              )}
              {!column.nullable && (
                <span className="px-1 py-0.5 bg-red-500/20 text-red-400 rounded text-xs">NOT NULL</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <Handle
        type="target"
        position={Position.Left}
        className="w-3 h-3 bg-blue-500"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="w-3 h-3 bg-purple-500"
      />
    </div>
  )
}

// Memoized nodeTypes outside component
const nodeTypes = {
  tableNode: TableNode,
}

interface ERDiagramProps {
  schema: DatabaseSchema
  onFullscreen?: () => void
  onDownloadPNG?: () => void
}

const ERDiagram = forwardRef<{ openFullscreen: () => void; downloadPNG: () => void }, ERDiagramProps>(
  ({ schema, onFullscreen, onDownloadPNG }, ref) => {
    const reactFlowRef = useRef<HTMLDivElement>(null)
    const [isFullscreen, setIsFullscreen] = useState(false)

    const openFullscreen = useCallback(() => {
      setIsFullscreen(true)
      onFullscreen?.()
    }, [onFullscreen])

    const closeFullscreen = useCallback(() => {
      setIsFullscreen(false)
    }, [])

    const downloadPNG = useCallback(async () => {
      if (!reactFlowRef.current) return

      try {
        const { toPng } = await import('html-to-image')
        const dataUrl = await toPng(reactFlowRef.current, {
          backgroundColor: '#0f172a',
          width: reactFlowRef.current.offsetWidth,
          height: reactFlowRef.current.offsetHeight,
          style: {
            transform: 'scale(1)',
            transformOrigin: 'top left',
          }
        })

        const link = document.createElement('a')
        link.download = `er-diagram-${new Date().getTime()}.png`
        link.href = dataUrl
        link.click()

        onDownloadPNG?.()
      } catch (error) {
        console.error('PNG export failed:', error)
      }
    }, [onDownloadPNG])

    useImperativeHandle(ref, () => ({
      openFullscreen,
      downloadPNG,
    }))

    // Handle ESC key to close fullscreen
    useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && isFullscreen) {
          closeFullscreen()
        }
      }

      if (isFullscreen) {
        document.addEventListener('keydown', handleKeyDown)
        return () => document.removeEventListener('keydown', handleKeyDown)
      }
    }, [isFullscreen, closeFullscreen])

    // Memoized layout generation
    const generateAutoLayout = useCallback((tables: TableType[]) => {
      const positions: { [key: string]: { x: number; y: number } } = {}
      const spacing = 350
      const cols = Math.ceil(Math.sqrt(tables.length))
      
      tables.forEach((table, index) => {
        const row = Math.floor(index / cols)
        const col = index % cols
        positions[table.name] = {
          x: col * spacing + 50,
          y: row * spacing + 50,
        }
      })
      
      return positions
    }, [])

    // Memoized initial nodes
    const initialNodes: Node[] = useMemo(() => {
      const positions = generateAutoLayout(schema.tables)
      
      return schema.tables.map((table) => ({
        id: table.name,
        type: 'tableNode',
        position: positions[table.name],
        data: { table },
        draggable: true,
      }))
    }, [schema.tables, generateAutoLayout])

    // Memoized initial edges
    const initialEdges: Edge[] = useMemo(() => {
      return schema.relationships.map((rel, index) => ({
        id: `${rel.from.table}-${rel.from.column}-${rel.to.table}-${rel.to.column}-${index}`,
        source: rel.from.table,
        target: rel.to.table,
        type: 'smoothstep',
        animated: true,
        style: {
          stroke: '#8b5cf6',
          strokeWidth: 2,
        },
        label: `${rel.from.column} → ${rel.to.column}`,
        labelStyle: {
          fill: '#e2e8f0',
          fontSize: 12,
          fontWeight: 500,
        },
        labelBgStyle: {
          fill: '#1e293b',
          fillOpacity: 0.8,
        },
      }))
    }, [schema.relationships])

    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

    const onConnect = useCallback(
      (params: Connection) => setEdges((eds) => addEdge(params, eds)),
      [setEdges]
    )

    if (schema.tables.length === 0) {
      return (
        <div className="h-full flex items-center justify-center text-slate-400">
          <div className="text-center">
            <Database className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p>Nenhuma tabela para exibir</p>
          </div>
        </div>
      )
    }

    return (
      <>
        {/* Modal Fullscreen Overlay via Portal */}
        {isFullscreen && createPortal(
          <div className="fixed inset-0 z-[9999] bg-slate-900">
            {/* Fullscreen Controls */}
            <div className="absolute top-4 right-4 z-50 flex gap-2">
              <button
                onClick={downloadPNG}
                className="bg-slate-800 border border-slate-600 text-slate-200 px-3 py-2 rounded-lg text-sm hover:bg-slate-700 transition-colors flex items-center gap-2"
              >
                📥 Download PNG
              </button>
              <button
                onClick={closeFullscreen}
                className="bg-slate-800 border border-slate-600 text-slate-200 px-3 py-2 rounded-lg text-sm hover:bg-slate-700 transition-colors flex items-center gap-2"
              >
                ❌ Fechar Fullscreen
              </button>
            </div>

            {/* Info Panel for Fullscreen */}
            <div className="absolute top-4 left-4 z-50 bg-slate-800 border border-slate-600 text-slate-200 p-3 rounded-lg text-sm max-w-xs">
              <div className="font-bold mb-2">📊 Diagrama ER - Fullscreen</div>
              <div>🖱️ Arrastar: Move tabelas</div>
              <div>🔍 Scroll: Zoom in/out</div>
              <div>⚡ Espaço: Centralizar</div>
              <div>⌨️ ESC: Sair do fullscreen</div>
              <div className="mt-2 text-slate-400">
                {schema.tables.length} tabelas • {schema.relationships.length} relacionamentos
              </div>
            </div>

            {/* Fullscreen Diagram - MESMA INSTÂNCIA */}
            <div ref={isFullscreen ? reactFlowRef : undefined} className="h-full w-full">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
                attributionPosition="bottom-left"
                className="bg-slate-900"
              >
                <Controls 
                  className={`${styles.reactFlowControls} bg-slate-800 border border-slate-600`}
                />
                <MiniMap 
                  className={`${styles.reactFlowMinimap} bg-slate-800 border border-slate-600`}
                  nodeColor="#3730a3"
                  maskColor="rgba(15, 23, 42, 0.8)"
                />
                <Background 
                  color="#475569" 
                  gap={20} 
                  size={1}
                />
              </ReactFlow>
            </div>
          </div>,
          document.body
        )}

        {/* Normal Diagram - MESMA INSTÂNCIA */}
        {!isFullscreen && (
          <div className="h-full w-full bg-slate-900 rounded-xl overflow-hidden">
            <div ref={reactFlowRef} className="h-full w-full">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
                attributionPosition="bottom-left"
                className="bg-slate-900"
              >
                <Controls 
                  className={`${styles.reactFlowControls} bg-slate-800 border border-slate-600`}
                />
                {/* MiniMap removido da versão normal */}
                <Background 
                  color="#475569" 
                  gap={20} 
                  size={1}
                />
              </ReactFlow>
            </div>
          </div>
        )}
      </>
    )
  }
)

ERDiagram.displayName = 'ERDiagram'

export default ERDiagram