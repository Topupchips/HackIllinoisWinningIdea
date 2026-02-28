import { useState } from 'react';
import { getCompoundByName } from '../services/api';
import './QuickAddChips.css';

const QUICK_DRUGS = ['Aspirin', 'Ibuprofen', 'Warfarin', 'Metformin'];

interface QuickAddChipsProps {
  onAdd: (m: { name: string; smiles: string; formula: string }) => void;
}

export default function QuickAddChips({ onAdd }: QuickAddChipsProps) {
  const [loading, setLoading] = useState<string | null>(null);

  const handleAdd = async (name: string) => {
    setLoading(name);
    const compound = await getCompoundByName(name);
    setLoading(null);
    if (compound?.smiles) {
      onAdd({
        name: compound.name,
        smiles: compound.smiles,
        formula: compound.formula,
      });
    }
  };

  return (
    <div className="quick-add-chips">
      <span className="quick-add-label">Quick add:</span>
      {QUICK_DRUGS.map((name) => (
        <button
          key={name}
          type="button"
          className="quick-add-chip"
          onClick={() => handleAdd(name)}
          disabled={!!loading}
        >
          {loading === name ? '...' : name}
        </button>
      ))}
    </div>
  );
}
