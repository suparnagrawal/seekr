import React from 'react';
import { Card, CardHeader, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { motion } from 'framer-motion';

interface ComparisonData {
  [tag: string]: {
    tag: string;
    name: string;
    type: string;
    description: string;
    specifications: {
      [rel: string]: {
        value: string;
        description: string;
      };
    };
  };
}

export function ComparisonTable({ data }: { data: ComparisonData }) {
  if (!data || Object.keys(data).length === 0) return null;

  const entities = Object.values(data);
  const allSpecs = new Set<string>();
  entities.forEach(ent => {
    Object.keys(ent.specifications || {}).forEach(spec => allSpecs.add(spec));
  });
  
  const specKeys = Array.from(allSpecs).sort();

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="my-4 w-full overflow-x-auto"
    >
      <Card className="border border-seekr-dark-700 bg-seekr-dark-800 shadow-xl overflow-hidden">
        <CardHeader className="bg-seekr-dark-900 border-b border-seekr-dark-700 py-3">
          <h3 className="text-sm font-semibold text-seekr-light-100 flex items-center gap-2">
            <svg className="w-4 h-4 text-seekr-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Comparative Specification Analysis
          </h3>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase bg-seekr-dark-900 text-seekr-dark-300">
              <tr>
                <th scope="col" className="px-4 py-3 border-r border-seekr-dark-700 font-medium">Specification</th>
                {entities.map(ent => (
                  <th key={ent.tag} scope="col" className="px-4 py-3 font-medium border-r border-seekr-dark-700 last:border-0 min-w-[200px]">
                    <div className="flex flex-col gap-1">
                      <span className="text-seekr-light-100">{ent.name || ent.tag}</span>
                      <Badge variant="outline" className="w-fit text-[10px] border-seekr-accent/30 text-seekr-accent">{ent.type}</Badge>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {specKeys.length === 0 ? (
                <tr>
                  <td colSpan={entities.length + 1} className="px-4 py-8 text-center text-seekr-dark-300">
                    No specifications extracted for these entities.
                  </td>
                </tr>
              ) : (
                specKeys.map((spec, idx) => (
                  <tr key={spec} className={`border-b border-seekr-dark-700 last:border-0 ${idx % 2 === 0 ? 'bg-seekr-dark-800' : 'bg-seekr-dark-800/50'}`}>
                    <td className="px-4 py-3 border-r border-seekr-dark-700 font-medium text-seekr-dark-200">
                      {spec.replace(/_/g, ' ')}
                    </td>
                    {entities.map(ent => {
                      const s = ent.specifications?.[spec];
                      return (
                        <td key={`${ent.tag}-${spec}`} className="px-4 py-3 border-r border-seekr-dark-700 last:border-0 align-top">
                          {s ? (
                            <div className="flex flex-col gap-1">
                              <span className="text-seekr-light-100 font-medium">{s.value}</span>
                              {s.description && (
                                <span className="text-xs text-seekr-dark-300 leading-snug">{s.description}</span>
                              )}
                            </div>
                          ) : (
                            <span className="text-seekr-dark-400 text-xs italic">-</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </motion.div>
  );
}
