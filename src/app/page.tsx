'use client'

import { useState } from 'react'
import { Database, FileText, Zap, Code2, ArrowRight, Maximize, Eye, Download } from 'lucide-react'
import { SQLParser } from '../lib/sqlParser'
import { DatabaseSchema } from '../types/Table'
import ERDiagramWrapper from '../components/ERDiagramWrapper'

export default function Home() {
  const [sqlInput, setSqlInput] = useState('')
  const [schema, setSchema] = useState<DatabaseSchema | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [viewMode, setViewMode] = useState<'list' | 'diagram'>('diagram')
  const [diagramRef, setDiagramRef] = useState<{ openFullscreen: () => void; downloadPNG: () => void } | null>(null)

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

  return (
    <div className="min-h-screen bg-slate-950 text-white relative overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 via-purple-600/20 to-cyan-600/20"></div>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(120,119,198,0.3),rgba(255,255,255,0))]"></div>
      
      <div className="relative z-10 container mx-auto px-6 py-12">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-6xl font-black bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent mb-6">
            SQL to ER Diagram
          </h1>
          <p className="text-xl text-slate-300 max-w-2xl mx-auto leading-relaxed">
            Transforme seus scripts SQL em <span className="text-purple-400 font-semibold">diagramas relacionais</span> automaticamente
          </p>
        </div>

        {/* Main Interface */}
        <div className="grid lg:grid-cols-2 gap-8 max-w-7xl mx-auto mb-16">
          {/* SQL Input */}
          <div className="group">
            <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-700/50 rounded-2xl p-8 shadow-2xl hover:shadow-purple-500/10 transition-all duration-500">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center">
                  <div className="p-2 bg-blue-500/20 rounded-lg mr-3">
                    <Code2 className="w-5 h-5 text-blue-400" />
                  </div>
                  <h2 className="text-2xl font-bold text-white">
                    Cole seu Script SQL
                  </h2>
                </div>
                <div className="flex items-center text-sm text-slate-400">
                  <span className="w-2 h-2 bg-green-400 rounded-full mr-2"></span>
                  PostgreSQL • MySQL • SQLServer
                </div>
              </div>
              
              <div className="relative">
                <textarea
                  value={sqlInput}
                  onChange={(e) => setSqlInput(e.target.value)}
                  placeholder="-- Cole seu SQL aqui
CREATE TABLE usuarios (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  email VARCHAR(100) UNIQUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE posts (
  id SERIAL PRIMARY KEY,
  usuario_id INTEGER NOT NULL,
  titulo VARCHAR(200) NOT NULL,
  conteudo TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);"
                  className="w-full h-96 p-6 bg-slate-800/80 border border-slate-600/50 rounded-xl 
                           font-mono text-sm text-slate-100 placeholder-slate-500 resize-none 
                           focus:ring-2 focus:ring-purple-500 focus:border-transparent 
                           focus:bg-slate-800 transition-all duration-300
                           shadow-inner overflow-y-auto"
                  style={{ 
                    lineHeight: '1.6',
                    fontSize: '14px'
                  }}
                />
              </div>
              
              <button
                onClick={handleConvert}
                disabled={!sqlInput.trim() || isProcessing}
                className="mt-6 w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 
                         disabled:from-slate-700 disabled:to-slate-600 disabled:cursor-not-allowed
                         text-white font-bold py-4 px-8 rounded-xl transition-all duration-300
                         flex items-center justify-center group shadow-lg hover:shadow-purple-500/25
                         transform hover:scale-[1.02] active:scale-[0.98]"
              >
                <Zap className={`w-5 h-5 mr-3 ${isProcessing ? 'animate-spin' : ''}`} />
                {isProcessing ? 'Processando...' : 'Gerar Diagrama'}
                <ArrowRight className="w-5 h-5 ml-3 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          </div>

          {/* Diagram Output */}
          <div className="group">
            <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-700/50 rounded-2xl p-8 shadow-2xl hover:shadow-cyan-500/10 transition-all duration-500">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center">
                  <div className="p-2 bg-cyan-500/20 rounded-lg mr-3">
                    <Database className="w-5 h-5 text-cyan-400" />
                  </div>
                  <h2 className="text-2xl font-bold text-white">
                    Diagrama ER
                  </h2>
                </div>
                
                <div className="flex space-x-2">
                  {schema && (
                    <>
                      <button 
                        onClick={() => setViewMode(viewMode === 'diagram' ? 'list' : 'diagram')}
                        className={`p-2 rounded-lg transition-colors ${
                          viewMode === 'diagram' 
                            ? 'bg-cyan-500/20 text-cyan-400' 
                            : 'bg-slate-700/50 hover:bg-slate-600/50 text-slate-400'
                        }`}
                        title={viewMode === 'diagram' ? 'Ver como lista' : 'Ver como diagrama'}
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button 
                        onClick={handleDownloadPNG}
                        className="p-2 bg-slate-700/50 hover:bg-slate-600/50 rounded-lg transition-colors"
                        title="Baixar PNG"
                      >
                        <Download className="w-4 h-4 text-slate-400" />
                      </button>
                      <button 
                        onClick={handleFullscreen}
                        className="p-2 bg-slate-700/50 hover:bg-slate-600/50 rounded-lg transition-colors"
                        title="Abrir em tela cheia"
                      >
                        <Maximize className="w-4 h-4 text-slate-400" />
                      </button>
                    </>
                  )}
                </div>
              </div>
              
              <div className="h-96 border-2 border-dashed border-slate-600/50 rounded-xl 
                            bg-gradient-to-br from-slate-800/30 to-slate-900/30 relative overflow-hidden">
                
                {schema ? (
                  viewMode === 'diagram' ? (
                    <ERDiagramWrapper schema={schema} onRef={setDiagramRef} />
                  ) : (
                    <div className="absolute inset-0 p-4">
                      <div className="h-full overflow-y-auto overflow-x-hidden pr-2">
                        <div className="space-y-4">
                          {schema.tables.map((table, index) => (
                            <div key={index} className="bg-slate-800/50 rounded-lg p-4 border border-slate-600/30">
                              <h3 className="font-bold text-white mb-2 flex items-center">
                                <Database className="w-4 h-4 mr-2 text-blue-400" />
                                {table.name}
                              </h3>
                              <div className="space-y-1">
                                {table.columns.map((column, colIndex) => (
                                  <div key={colIndex} className="flex items-center justify-between text-sm">
                                    <span className="text-slate-300 flex-1 min-w-0">
                                      <span className={column.primaryKey ? 'text-yellow-400 font-semibold' : ''}>{column.name}</span>
                                      <span className="text-slate-500 ml-2">{column.type}</span>
                                    </span>
                                    <div className="flex space-x-1 flex-shrink-0 ml-2">
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
                            </div>
                          ))}
                          
                          {schema.relationships.length > 0 && (
                            <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-600/30">
                              <h3 className="font-bold text-white mb-2 flex items-center">
                                <ArrowRight className="w-4 h-4 mr-2 text-green-400" />
                                Relacionamentos ({schema.relationships.length})
                              </h3>
                              <div className="space-y-1">
                                {schema.relationships.map((rel, index) => (
                                  <div key={index} className="text-sm text-slate-300">
                                    <span className="text-blue-400">{rel.from.table}.{rel.from.column}</span>
                                    <span className="mx-2 text-slate-500">→</span>
                                    <span className="text-purple-400">{rel.to.table}.{rel.to.column}</span>
                                    <span className="ml-2 text-xs text-slate-500">({rel.type})</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                      <Database className="w-20 h-20 mx-auto text-slate-600 mb-6" />
                      <h3 className="text-xl font-bold text-slate-300 mb-2">
                        Pronto para gerar seu diagrama
                      </h3>
                      <p className="text-slate-500 mb-4">
                        Cole seu SQL e veja o diagrama aparecer automaticamente
                      </p>
                      <div className="flex items-center justify-center space-x-4 text-xs text-slate-600">
                        <span>• Auto-layout inteligente</span>
                        <span>• Relacionamentos detectados</span>
                        <span>• Exportação em alta qualidade</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          <div className="group cursor-pointer">
            <div className="bg-slate-900/30 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-8 text-center h-full
                          hover:bg-slate-800/50 transition-all duration-500 hover:scale-105 hover:shadow-2xl hover:shadow-blue-500/10">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl 
                            flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300">
                <Zap className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-bold text-white mb-3">Detecção Inteligente</h3>
              <p className="text-slate-400 leading-relaxed">
                Detecta relacionamentos complexos, foreign keys e convenções de nomenclatura automaticamente
              </p>
            </div>
          </div>
          
          <div className="group cursor-pointer">
            <div className="bg-slate-900/30 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-8 text-center h-full
                          hover:bg-slate-800/50 transition-all duration-500 hover:scale-105 hover:shadow-2xl hover:shadow-purple-500/10">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl 
                            flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300">
                <Database className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-bold text-white mb-3">Multi-Engine</h3>
              <p className="text-slate-400 leading-relaxed">
                Suporte completo para PostgreSQL, MySQL, SQL Server e outras engines de banco
              </p>
            </div>
          </div>
          
          <div className="group cursor-pointer">
            <div className="bg-slate-900/30 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-8 text-center h-full
                          hover:bg-slate-800/50 transition-all duration-500 hover:scale-105 hover:shadow-2xl hover:shadow-cyan-500/10">
              <div className="w-16 h-16 bg-gradient-to-br from-cyan-500 to-cyan-600 rounded-2xl 
                            flex items-center justify-center mx-auto mb-6 group-hover:scale-110 transition-transform duration-300">
                <FileText className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-xl font-bold text-white mb-3">Export Pro</h3>
              <p className="text-slate-400 leading-relaxed">
                Exporte em PNG 4K, SVG vetorial, PDF de alta qualidade e links compartilháveis
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-16 pt-8 border-t border-slate-700/30">
          <p className="text-slate-500">
            Feito com Next.js, TypeScript e Tailwind CSS
          </p>
        </div>
      </div>
    </div>
  )
}