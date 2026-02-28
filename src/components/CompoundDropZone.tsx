import { useState } from 'react';
import { Trash2, Beaker, Search } from 'lucide-react';
import Structure2D from './Structure2D';
import { getCompoundByName } from '../services/api';
import './CompoundDropZone.css';

interface Medication {
  id: string;
  name: string;
  smiles: string;
  formula: string;
  compoundType: string;
}

interface CompoundDropZoneProps {
  medications: Medication[];
  onAdd: (m: { name: string; smiles: string; formula: string }) => void;
  onRemove: (id: string) => void;
  onSimilar?: (name: string, smiles: string) => void;
}

export default function CompoundDropZone({ medications, onAdd, onRemove, onSimilar }: CompoundDropZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [dropping, setDropping] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const name = e.dataTransfer.getData('drug_name');
    if (!name) return;
    setDropping(true);
    const compound = await getCompoundByName(name);
    setDropping(false);
    if (compound?.smiles) {
      onAdd({
        name: compound.name,
        smiles: compound.smiles,
        formula: compound.formula,
      });
    }
  };

  return (
    <div
      className={`compound-drop-zone ${dragOver ? 'drag-over' : ''} ${medications.length === 0 ? 'empty' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {medications.length === 0 ? (
        <div className="drop-zone-placeholder">
          <Beaker size={40} />
          <p>Drop compounds here</p>
          <span>or search / tap quick-add below</span>
        </div>
      ) : (
        <div className="drop-zone-cards">
          {medications.map((m) => (
            <div key={m.id} className="compound-card">
              <div className="compound-card-structure">
                <Structure2D smiles={m.smiles} name={m.name} size={70} />
              </div>
              <span className="compound-card-name">{m.name}</span>
              <div className="compound-card-actions">
                {onSimilar && (
                  <button
                    type="button"
                    className="compound-card-similar"
                    onClick={() => onSimilar(m.name, m.smiles)}
                    aria-label="Find similar"
                    title="Find similar drugs"
                  >
                    <Search size={14} />
                  </button>
                )}
                <button
                  type="button"
                  className="compound-card-remove"
                  onClick={() => onRemove(m.id)}
                  aria-label="Remove"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {dropping && (
        <div className="drop-zone-loading">
          <span>Adding...</span>
        </div>
      )}
    </div>
  );
}
