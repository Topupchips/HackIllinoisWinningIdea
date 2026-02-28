import { useState } from 'react';
import { getStructureImageUrl } from '../services/pubchem';
import './Structure2D.css';

interface Structure2DProps {
  smiles: string;
  name?: string;
  size?: number;
}

export default function Structure2D({ smiles, name, size = 120 }: Structure2DProps) {
  const [error, setError] = useState(false);

  if (!smiles?.trim()) return null;

  const url = getStructureImageUrl(smiles, size);

  return (
    <div className="structure-2d">
      {!error ? (
        <img
          src={url}
          alt={name ? `Structure of ${name}` : 'Molecular structure'}
          onError={() => setError(true)}
          className="structure-2d-img"
        />
      ) : (
        <div className="structure-2d-fallback">
          <code>{smiles.length > 30 ? `${smiles.slice(0, 30)}...` : smiles}</code>
        </div>
      )}
    </div>
  );
}
