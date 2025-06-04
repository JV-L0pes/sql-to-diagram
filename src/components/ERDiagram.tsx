// src/components/ERDiagram.tsx
'use client'

import { useCallback, useMemo, useRef, useImperativeHandle, forwardRef } from 'react'
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

// Componente customizado para nós de tabela
function TableNode({ data }: { data: { table: TableType } }) {
  const { table } = data

  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg shadow-lg min-w-[250px]">
      {/* Header da tabela */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-4 py-2 rounded-t-lg">
        <div className="flex items-center text-white font-bold">
          <Database className="w-4 h-4 mr-2" />
          {table.name}
        </div>
      </div>
      
      {/* Colunas */}
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

      {/* Handles para conexões */}
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

// Tipos de nós customizados
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

    const openFullscreen = useCallback(() => {
      // Criar HTML do diagrama ER para nova aba
      const diagramHTML = `
        <!DOCTYPE html>
        <html>
          <head>
            <title>ER Diagram - Fullscreen</title>
            <meta charset="utf-8">
            <style>
              * { margin: 0; padding: 0; box-sizing: border-box; }
              body { 
                background: #0f172a; 
                font-family: system-ui, -apple-system, sans-serif;
                overflow-x: auto;
                padding: 20px;
              }
              .diagram-container {
                display: flex;
                flex-wrap: wrap;
                gap: 30px;
                justify-content: center;
                align-items: flex-start;
                min-height: calc(100vh - 40px);
                padding: 20px;
              }
              .table {
                background: #1e293b;
                border: 1px solid #475569;
                border-radius: 12px;
                min-width: 280px;
                box-shadow: 0 8px 25px rgba(0, 0, 0, 0.4);
                transition: transform 0.2s ease;
              }
              .table:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 35px rgba(0, 0, 0, 0.5);
              }
              .table-header {
                background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                color: white;
                padding: 16px 20px;
                font-weight: bold;
                font-size: 16px;
                border-radius: 12px 12px 0 0;
                display: flex;
                align-items: center;
              }
              .table-icon {
                margin-right: 10px;
                font-size: 18px;
              }
              .table-body {
                padding: 16px 20px;
              }
              .column {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 0;
                color: #e2e8f0;
                font-size: 14px;
                border-bottom: 1px solid #334155;
              }
              .column:last-child {
                border-bottom: none;
              }
              .column-info {
                display: flex;
                align-items: center;
                flex: 1;
              }
              .key-icon {
                color: #fbbf24;
                margin-right: 8px;
                font-size: 14px;
              }
              .column-name {
                font-weight: 500;
              }
              .column-name.pk {
                color: #fbbf24;
                font-weight: bold;
              }
              .column-type {
                color: #94a3b8;
                margin-left: 12px;
                font-size: 12px;
                font-style: italic;
              }
              .tags {
                display: flex;
                gap: 4px;
                margin-left: 8px;
              }
              .tag {
                padding: 3px 6px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                text-transform: uppercase;
              }
              .tag-pk { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
              .tag-fk { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
              .tag-nn { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
              .relationships {
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: rgba(30, 41, 59, 0.95);
                border: 1px solid #475569;
                border-radius: 12px;
                padding: 16px;
                max-width: 400px;
                max-height: 300px;
                overflow-y: auto;
                backdrop-filter: blur(10px);
              }
              .relationships h3 {
                color: #e2e8f0;
                margin-bottom: 12px;
                font-size: 14px;
                display: flex;
                align-items: center;
              }
              .relationship {
                color: #e2e8f0;
                padding: 4px 0;
                font-size: 12px;
                border-bottom: 1px solid #334155;
              }
              .relationship:last-child {
                border-bottom: none;
              }
              .rel-from { color: #3b82f6; font-weight: 500; }
              .rel-to { color: #8b5cf6; font-weight: 500; }
              .rel-arrow { color: #64748b; margin: 0 6px; }
              .title {
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(30, 41, 59, 0.95);
                color: #e2e8f0;
                padding: 12px 24px;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
                backdrop-filter: blur(10px);
                border: 1px solid #475569;
                z-index: 1000;
              }
              .instructions {
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(30, 41, 59, 0.95);
                color: #94a3b8;
                padding: 10px;
                border-radius: 8px;
                font-size: 12px;
                border: 1px solid #475569;
                backdrop-filter: blur(10px);
              }
            </style>
          </head>
          <body>
            <div class="title">📊 Diagrama ER</div>
            <div class="instructions">
              F11 para tela cheia total<br>
              ESC para sair
            </div>
            
            <div class="diagram-container">
              ${schema.tables.map(table => `
                <div class="table">
                  <div class="table-header">
                    <span class="table-icon">🗃️</span>
                    ${table.name}
                  </div>
                  <div class="table-body">
                    ${table.columns.map(column => `
                      <div class="column">
                        <div class="column-info">
                          ${column.primaryKey ? '<span class="key-icon">🔑</span>' : '<span style="width: 22px; display: inline-block;"></span>'}
                          <span class="column-name ${column.primaryKey ? 'pk' : ''}">${column.name}</span>
                          <span class="column-type">${column.type}</span>
                        </div>
                        <div class="tags">
                          ${column.primaryKey ? '<span class="tag tag-pk">PK</span>' : ''}
                          ${column.foreignKey ? '<span class="tag tag-fk">FK</span>' : ''}
                          ${!column.nullable ? '<span class="tag tag-nn">NOT NULL</span>' : ''}
                        </div>
                      </div>
                    `).join('')}
                  </div>
                </div>
              `).join('')}
            </div>
            
            ${schema.relationships.length > 0 ? `
              <div class="relationships">
                <h3>🔗 Relacionamentos (${schema.relationships.length})</h3>
                ${schema.relationships.map(rel => `
                  <div class="relationship">
                    <span class="rel-from">${rel.from.table}.${rel.from.column}</span>
                    <span class="rel-arrow">→</span>
                    <span class="rel-to">${rel.to.table}.${rel.to.column}</span>
                  </div>
                `).join('')}
              </div>
            ` : ''}
            
            <script>
              // Auto F11 para fullscreen
              document.addEventListener('keydown', function(e) {
                if (e.key === 'F11') {
                  e.preventDefault();
                  if (!document.fullscreenElement) {
                    document.documentElement.requestFullscreen();
                  } else {
                    document.exitFullscreen();
                  }
                }
              });
            </script>
          </body>
        </html>
      `
      
      const newWindow = window.open('', '_blank', 'width=1400,height=900')
      if (newWindow) {
        newWindow.document.write(diagramHTML)
        newWindow.document.close()
        newWindow.focus()
        
        // Tentar abrir em fullscreen automaticamente após um delay
        setTimeout(() => {
          if (newWindow.document.documentElement.requestFullscreen) {
            newWindow.document.documentElement.requestFullscreen().catch(() => {
              console.log('Fullscreen automático bloqueado, use F11')
            })
          }
        }, 1000)
      } else {
        alert('❌ Bloqueador de pop-up ativo. Permita pop-ups para esta página.')
      }

      if (onFullscreen) {
        onFullscreen()
      }
    }, [onFullscreen, schema])

    const downloadPNG = useCallback(async () => {
      if (!reactFlowRef.current) return

      try {
        // Usar Screen Capture API simplificada
        if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {
          const stream = await navigator.mediaDevices.getDisplayMedia({
            video: true
          })
          
          const video = document.createElement('video')
          video.srcObject = stream
          video.play()
          
          video.onloadedmetadata = () => {
            const canvas = document.createElement('canvas')
            canvas.width = video.videoWidth
            canvas.height = video.videoHeight
            
            const ctx = canvas.getContext('2d')
            if (ctx) {
              ctx.drawImage(video, 0, 0)
              
              // Parar gravação
              stream.getTracks().forEach(track => track.stop())
              
              // Download
              const link = document.createElement('a')
              link.download = `er-diagram-${new Date().getTime()}.png`
              link.href = canvas.toDataURL('image/png')
              link.click()
            }
          }
        } else {
          throw new Error('API não suportada')
        }

        if (onDownloadPNG) {
          onDownloadPNG()
        }
      } catch (error) {
        console.error('Erro ao capturar:', error)
        alert('📸 Para capturar PNG:\n\n1. Clique em "Compartilhar tela"\n2. Selecione esta aba do navegador\n3. A imagem será salva automaticamente\n\nOu use Print Screen manualmente!')
      }
    }, [onDownloadPNG])

    useImperativeHandle(ref, () => ({
      openFullscreen,
      downloadPNG,
    }))

    // Gerar posições automáticas para as tabelas
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

    // Converter schema para nós do React Flow
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

    // Converter relacionamentos para edges
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
      </div>
    )
  }
)

ERDiagram.displayName = 'ERDiagram'

export default ERDiagram