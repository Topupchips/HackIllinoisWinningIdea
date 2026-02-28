import { Dna } from 'lucide-react';
import './GeneVisual.css';

interface GeneVisualProps {
  name: string;
  phenotype: string;
  enzyme: string;
  selected: boolean;
}

const PHENOTYPE_COLORS: Record<string, string> = {
  Extensive: '#22c55e',
  Intermediate: '#eab308',
  Poor: '#ef4444',
  Ultrarapid: '#3b82f6',
};

const PHENOTYPE_LEVEL: Record<string, number> = {
  Poor: 0.25,
  Intermediate: 0.5,
  Extensive: 0.85,
  Ultrarapid: 1,
};

export default function GeneVisual({ name, phenotype, enzyme, selected }: GeneVisualProps) {
  const color = PHENOTYPE_COLORS[phenotype] || '#14b8a6';
  const level = PHENOTYPE_LEVEL[phenotype] ?? 0.5;

  return (
    <div className={`gene-visual ${selected ? 'selected' : ''}`}>
      <div className="gene-icon" style={{ borderColor: color }}>
        <Dna size={20} color={color} />
      </div>
      <div className="gene-info">
        <span className="gene-name">{name}</span>
        <span className="gene-enzyme">{enzyme}</span>
        <div className="gene-metabolism">
          <div className="metabolism-bar">
            <div
              className="metabolism-fill"
              style={{ width: `${level * 100}%`, background: color }}
            />
          </div>
          <span className="metabolism-label">{phenotype}</span>
        </div>
      </div>
    </div>
  );
}
