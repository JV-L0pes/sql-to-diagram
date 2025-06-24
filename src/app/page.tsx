'use client'

import { useState, useEffect } from 'react'
import { Database, Code2, Zap, ArrowRight, Download, Maximize, Eye, Sparkles, Terminal, GitBranch, Network } from 'lucide-react'
import { SQLParser } from '../lib/sqlParser'
import { DatabaseSchema } from '../types/Table'
import ERDiagramWrapper from '../components/ERDiagramWrapper'

export default function Home() {
  const [sqlInput, setSqlInput] = useState('')
  const [schema, setSchema] = useState<DatabaseSchema | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [viewMode, setViewMode] = useState<'list' | 'diagram'>('diagram')
  const [diagramRef, setDiagramRef] = useState<{ openFullscreen: () => void; downloadPNG: () => void } | null>(null)
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 })

  // Efeito de movimento do mouse para elementos interativos
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY })
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  const handleConvert = async () => {
    if (!sqlInput.trim()) return
    
    setIsProcessing(true)
    
    try {
      const parser = new SQLParser()
      const result = parser.parseSQLScript(sqlInput)
      setSchema(result)
      console.log('Schema gerado:', result)
    } catch (error) {
      console.error('Erro ao processar SQL:', error)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleFullscreen = () => {
    if (diagramRef) {
      diagramRef.openFullscreen()
    }
  }

  const handleDownloadPNG = () => {
    if (diagramRef) {
      diagramRef.downloadPNG()
    }
  }

  const sqlPlaceholder = `-- Transforme seu SQL em arte visual
CREATE TABLE usuarios (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  nome VARCHAR(100) NOT NULL,
  avatar_url TEXT,
  criado_em TIMESTAMP DEFAULT NOW(),
  ativo BOOLEAN DEFAULT true
);

CREATE TABLE projetos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id INTEGER NOT NULL,
  titulo VARCHAR(200) NOT NULL,
  descricao TEXT,
  tecnologias JSONB,
  repositorio_url TEXT,
  status VARCHAR(20) DEFAULT 'ativo',
  criado_em TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE colaboradores (
  projeto_id UUID NOT NULL,
  usuario_id INTEGER NOT NULL,
  papel VARCHAR(50) DEFAULT 'desenvolvedor',
  adicionado_em TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (projeto_id, usuario_id),
  FOREIGN KEY (projeto_id) REFERENCES projetos(id),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);`

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-black to-gray-900 text-white relative overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0">
        {/* Grid Pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(rgba(0,255,157,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,157,0.03)_1px,transparent_1px)] bg-[size:50px_50px]"></div>
        
        {/* Animated Orbs */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl animate-pulse delay-1000"></div>
        <div className="absolute top-1/2 left-1/2 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl animate-pulse delay-2000"></div>
        
        {/* Mouse Follower Glow */}
        <div 
          className="absolute w-96 h-96 bg-emerald-400/5 rounded-full blur-3xl pointer-events-none transition-all duration-300 ease-out"
          style={{
            left: mousePosition.x - 192,
            top: mousePosition.y - 192,
          }}
        ></div>
      </div>

      <div className="relative z-10 container mx-auto px-6 py-8">
        {/* Header Futurista */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-3 mb-6 px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full backdrop-blur-sm">
            <Sparkles className="w-4 h-4 text-emerald-400 animate-pulse" />
            <span className="text-sm font-mono text-emerald-300">SQL → VISUAL</span>
            <Sparkles className="w-4 h-4 text-emerald-400 animate-pulse" />
          </div>
          
          <h1 className="text-7xl font-black mb-6 bg-gradient-to-r from-emerald-400 via-cyan-400 to-purple-400 bg-clip-text text-transparent tracking-tight">
            SQL Architect
          </h1>
          
          <p className="text-xl text-gray-300 max-w-3xl mx-auto leading-relaxed mb-8">
            Transforme seus scripts de banco em <span className="text-emerald-400 font-semibold">diagramas relacionais interativos</span> com precisão milimétrica e design de próxima geração
          </p>

          {/* Stats */}
          <div className="flex justify-center gap-8 text-sm">
            <div className="flex items-center gap-2 text-gray-400">
              <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
              <span>PostgreSQL • MySQL • SQLServer</span>
            </div>
            <div className="flex items-center gap-2 text-gray-400">
              <div className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
              <span>Auto-layout • Export 4K • Real-time</span>
            </div>
          </div>
        </div>

        {/* Interface Principal */}
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-8 mb-16">
            
            {/* SQL Input - Redesign Completo */}
            <div className="group">
              <div className="relative">
                {/* Border glow effect */}
                <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/20 via-cyan-500/20 to-purple-500/20 rounded-3xl blur-xl group-hover:blur-2xl transition-all duration-500"></div>
                
                <div className="relative bg-gray-900/80 backdrop-blur-xl border border-gray-700/50 rounded-3xl overflow-hidden shadow-2xl">
                  {/* Header com tabs */}
                  <div className="flex items-center justify-between p-6 border-b border-gray-700/50">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-3">
                        <div className="relative">
                          <Terminal className="w-6 h-6 text-emerald-400" />
                          <div className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 rounded-full animate-ping"></div>
                        </div>
                        <div>
                          <h2 className="text-xl font-bold text-white">SQL Input</h2>
                          <p className="text-xs text-gray-400 font-mono">PARSING ENGINE v2.0</p>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex gap-2">
                      <div className="w-3 h-3 bg-red-400 rounded-full"></div>
                      <div className="w-3 h-3 bg-yellow-400 rounded-full"></div>
                      <div className="w-3 h-3 bg-emerald-400 rounded-full"></div>
                    </div>
                  </div>

                  {/* Code Editor */}
                  <div className="p-6">
                    <div className="relative">
                      <textarea
                        value={sqlInput}
                        onChange={(e) => setSqlInput(e.target.value)}
                        placeholder={sqlPlaceholder}
                        className="w-full h-96 p-6 bg-black/50 border border-gray-600/30 rounded-2xl 
                                 font-mono text-sm text-gray-100 placeholder-gray-500 resize-none 
                                 focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 
                                 focus:bg-black/70 transition-all duration-300 shadow-inner
                                 leading-relaxed"
                        style={{ fontSize: '14px', lineHeight: '1.8' }}
                      />
                      
                    </div>

                    {/* Action Button */}
                    <button
                      onClick={handleConvert}
                      disabled={!sqlInput.trim() || isProcessing}
                      className="mt-6 w-full relative group/btn overflow-hidden"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-emerald-600 via-cyan-600 to-purple-600 rounded-2xl blur-lg group-hover/btn:blur-xl transition-all duration-300"></div>
                      <div className="relative bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 
                                    disabled:from-gray-700 disabled:to-gray-600 disabled:cursor-not-allowed
                                    text-white font-bold py-4 px-8 rounded-2xl transition-all duration-300
                                    flex items-center justify-center shadow-lg
                                    transform hover:scale-[1.02] active:scale-[0.98]">
                        
                        {isProcessing ? (
                          <>
                            <div className="w-5 h-5 mr-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                            Processando SQL...
                          </>
                        ) : (
                          <>
                            <Zap className="w-5 h-5 mr-3" />
                            Gerar Diagrama
                            <ArrowRight className="w-5 h-5 ml-3 group-hover/btn:translate-x-1 transition-transform" />
                          </>
                        )}
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Diagram Output - Redesign */}
            <div className="group">
              <div className="relative">
                {/* Border glow effect */}
                <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 via-purple-500/20 to-pink-500/20 rounded-3xl blur-xl group-hover:blur-2xl transition-all duration-500"></div>
                
                <div className="relative bg-gray-900/80 backdrop-blur-xl border border-gray-700/50 rounded-3xl overflow-hidden shadow-2xl">
                  {/* Header */}
                  <div className="flex items-center justify-between p-6 border-b border-gray-700/50">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-3">
                        <div className="relative">
                          <Network className="w-6 h-6 text-cyan-400" />
                          <div className="absolute -top-1 -right-1 w-3 h-3 bg-cyan-400 rounded-full animate-ping"></div>
                        </div>
                        <div>
                          <h2 className="text-xl font-bold text-white">ER Diagram</h2>
                          <p className="text-xs text-gray-400 font-mono">VISUAL ENGINE v3.0</p>
                        </div>
                      </div>
                    </div>

                    {/* Controls */}
                    <div className="flex gap-2">
                      {schema && (
                        <>
                          <button 
                            onClick={() => setViewMode(viewMode === 'diagram' ? 'list' : 'diagram')}
                            className={`p-2.5 rounded-xl transition-all duration-300 ${
                              viewMode === 'diagram' 
                                ? 'bg-cyan-500/20 text-cyan-400 shadow-lg shadow-cyan-500/20' 
                                : 'bg-gray-700/50 hover:bg-gray-600/50 text-gray-400'
                            }`}
                            title={viewMode === 'diagram' ? 'Ver como lista' : 'Ver como diagrama'}
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          <button 
                            onClick={handleDownloadPNG}
                            className="p-2.5 bg-gray-700/50 hover:bg-gray-600/50 rounded-xl transition-all duration-300 hover:shadow-lg"
                            title="Baixar PNG"
                          >
                            <Download className="w-4 h-4 text-gray-400" />
                          </button>
                          <button 
                            onClick={handleFullscreen}
                            className="p-2.5 bg-gray-700/50 hover:bg-gray-600/50 rounded-xl transition-all duration-300 hover:shadow-lg"
                            title="Tela cheia"
                          >
                            <Maximize className="w-4 h-4 text-gray-400" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Content */}
                  <div className="p-6">
                    <div className="h-96 border-2 border-dashed border-gray-600/30 rounded-2xl 
                                  bg-gradient-to-br from-gray-800/30 to-black/30 relative overflow-hidden">
                      
                      {schema ? (
                        viewMode === 'diagram' ? (
                          <ERDiagramWrapper schema={schema} onRef={setDiagramRef} />
                        ) : (
                          <div className="absolute inset-0 p-4">
                            <div className="h-full overflow-y-auto space-y-4">
                              {schema.tables.map((table, index) => (
                                <div key={index} className="bg-gray-800/50 rounded-xl p-4 border border-gray-600/30 backdrop-blur-sm">
                                  <h3 className="font-bold text-white mb-3 flex items-center">
                                    <Database className="w-4 h-4 mr-2 text-emerald-400" />
                                    {table.name}
                                    <span className="ml-auto text-xs text-gray-500">
                                      {table.columns.length} cols
                                    </span>
                                  </h3>
                                  <div className="space-y-2">
                                    {table.columns.map((column, colIndex) => (
                                      <div key={colIndex} className="flex items-center justify-between text-sm bg-black/20 rounded-lg p-2">
                                        <span className="text-gray-300 flex-1">
                                          <span className={column.primaryKey ? 'text-yellow-400 font-semibold' : ''}>{column.name}</span>
                                          <span className="text-gray-500 ml-2 font-mono text-xs">{column.type}</span>
                                        </span>
                                        <div className="flex gap-1">
                                          {column.primaryKey && (
                                            <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded-md text-xs font-mono">PK</span>
                                          )}
                                          {column.foreignKey && (
                                            <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 rounded-md text-xs font-mono">FK</span>
                                          )}
                                          {!column.nullable && (
                                            <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded-md text-xs font-mono">NN</span>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ))}
                              
                              {schema.relationships.length > 0 && (
                                <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-600/30 backdrop-blur-sm">
                                  <h3 className="font-bold text-white mb-3 flex items-center">
                                    <ArrowRight className="w-4 h-4 mr-2 text-green-400" />
                                    Relacionamentos ({schema.relationships.length})
                                  </h3>
                                  <div className="space-y-2">
                                    {schema.relationships.map((rel, index) => (
                                      <div key={index} className="text-sm text-gray-300 bg-black/20 rounded-lg p-2">
                                        <span className="text-cyan-400 font-mono">{rel.from.table}.{rel.from.column}</span>
                                        <span className="mx-2 text-gray-500">→</span>
                                        <span className="text-purple-400 font-mono">{rel.to.table}.{rel.to.column}</span>
                                        <span className="ml-2 text-xs text-gray-500 bg-gray-700/50 px-2 py-1 rounded">
                                          {rel.type}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )
                      ) : (
                        <div className="absolute inset-0 flex items-center justify-center">
                          <div className="text-center space-y-6">
                            <div className="relative">
                              <Database className="w-20 h-20 mx-auto text-gray-600" />
                              <div className="absolute inset-0 bg-gray-600/20 rounded-full blur-2xl"></div>
                            </div>
                            <div>
                              <h3 className="text-xl font-bold text-gray-300 mb-2">
                                Engine Aguardando Input
                              </h3>
                              <p className="text-gray-500 mb-4 max-w-xs mx-auto">
                                Cole seu SQL e observe a magia acontecer em tempo real
                              </p>
                              <div className="flex flex-wrap justify-center gap-3 text-xs text-gray-600">
                                <span className="flex items-center gap-1">
                                  <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full"></div>
                                  Layout Inteligente
                                </span>
                                <span className="flex items-center gap-1">
                                  <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full"></div>
                                  Detecção Auto
                                </span>
                                <span className="flex items-center gap-1">
                                  <div className="w-1.5 h-1.5 bg-purple-400 rounded-full"></div>
                                  Export 4K
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Features Grid Redesign */}
          <div className="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto mb-16">
            {[
              {
                icon: Zap,
                title: "AI-Powered Detection",
                description: "Engine de ML detecta padrões complexos, relacionamentos implícitos e convenções de nomenclatura automaticamente",
                color: "emerald",
                gradient: "from-emerald-500 to-emerald-600"
              },
              {
                icon: Database,
                title: "Multi-Engine Support", 
                description: "Compatibilidade total com PostgreSQL, MySQL, SQLServer, Oracle e outras engines enterprise",
                color: "cyan",
                gradient: "from-cyan-500 to-cyan-600"
              },
              {
                icon: Code2,
                title: "Professional Export",
                description: "Exportação em PNG 4K, SVG vetorial, PDF de alta qualidade e links compartilháveis em tempo real",
                color: "purple",
                gradient: "from-purple-500 to-purple-600"
              }
            ].map((feature, index) => (
              <div key={index} className="group cursor-pointer">
                <div className="relative">
                  <div className={`absolute inset-0 bg-gradient-to-r ${feature.gradient} opacity-10 rounded-3xl blur-xl group-hover:blur-2xl group-hover:opacity-20 transition-all duration-500`}></div>
                  
                  <div className="relative bg-gray-900/50 backdrop-blur-xl border border-gray-700/50 rounded-3xl p-8 h-full
                                hover:bg-gray-800/50 transition-all duration-500 hover:scale-105 hover:shadow-2xl">
                    
                    <div className={`w-16 h-16 bg-gradient-to-br ${feature.gradient} rounded-2xl 
                                  flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300
                                  shadow-lg`}>
                      <feature.icon className="w-8 h-8 text-white" />
                    </div>
                    
                    <h3 className="text-xl font-bold text-white mb-4 text-center">{feature.title}</h3>
                    <p className="text-gray-400 leading-relaxed text-center text-sm">
                      {feature.description}
                    </p>
                    
                    <div className="mt-6 flex justify-center">
                      <div className={`w-12 h-1 bg-gradient-to-r ${feature.gradient} rounded-full`}></div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="text-center pt-12 border-t border-gray-700/30">
            <div className="flex justify-center items-center gap-6 mb-6">
              <div className="flex items-center gap-2 text-gray-500 text-sm">
                <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
                <span className="font-mono">Next.js 15</span>
              </div>
              <div className="flex items-center gap-2 text-gray-500 text-sm">
                <div className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
                <span className="font-mono">TypeScript</span>
              </div>
              <div className="flex items-center gap-2 text-gray-500 text-sm">
                <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse"></div>
                <span className="font-mono">Tailwind CSS</span>
              </div>
            </div>
            <p className="text-gray-600 font-mono text-sm">
              Engineered for performance • Built for scale • Designed for devs
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}