import React from 'react';
import { ComparisonTable } from '@/components/entity/ComparisonTable';

interface ToolResultRendererProps {
  toolName: string;
  result: any;
}

export function ToolResultRenderer({ toolName, result }: ToolResultRendererProps) {
  if (!result || typeof result !== 'object') {
    return null;
  }

  // Register custom renderers for specific tools
  switch (toolName) {
    case 'compare_specs':
      if (result.data) {
        return (
          <div className="font-sans text-base w-full overflow-hidden mt-2">
            <ComparisonTable data={result.data} />
          </div>
        );
      }
      break;
    
    // Extensible for future tools:
    // case 'diagnostic_chart':
    //   return <DiagnosticChart data={result.data} />;
      
    default:
      return null;
  }
  
  return null;
}
