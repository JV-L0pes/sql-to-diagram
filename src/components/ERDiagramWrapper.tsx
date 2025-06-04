// src/components/ERDiagramWrapper.tsx
'use client'

import { ReactFlowProvider } from 'reactflow'
import { useRef, useEffect } from 'react'
import ERDiagram from './ERDiagram'
import { DatabaseSchema } from '../types/Table'

interface ERDiagramWrapperProps {
  schema: DatabaseSchema
  onRef?: (ref: { openFullscreen: () => void; downloadPNG: () => void } | null) => void
}

export default function ERDiagramWrapper({ schema, onRef }: ERDiagramWrapperProps) {
  const diagramRef = useRef<{ openFullscreen: () => void; downloadPNG: () => void } | null>(null)

  useEffect(() => {
    if (onRef && diagramRef.current) {
      onRef(diagramRef.current)
    }
  }, [onRef])

  const handleFullscreen = () => {
    console.log('Diagrama aberto em fullscreen!')
  }

  const handleDownloadPNG = () => {
    console.log('Download PNG iniciado!')
  }

  return (
    <ReactFlowProvider>
      <ERDiagram 
        ref={diagramRef}
        schema={schema} 
        onFullscreen={handleFullscreen}
        onDownloadPNG={handleDownloadPNG}
      />
    </ReactFlowProvider>
  )
}