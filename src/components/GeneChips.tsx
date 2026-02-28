import { useState } from 'react';
import './GeneChips.css';

interface GeneticVariant {
  id: string;
  name: string;
  enzyme: string;
  phenotype: string;
  selected: boolean;
}

const PHENOTYPES = ['Extensive', 'Intermediate', 'Poor', 'Ultrarapid'];

interface GeneChipsProps {
  variants: GeneticVariant[];
  onToggle: (id: string) => void;
  onPhenotypeChange: (id: string, phenotype: string) => void;
}

export default function GeneChips({ variants, onToggle, onPhenotypeChange }: GeneChipsProps) {
  const [openPhenotype, setOpenPhenotype] = useState<string | null>(null);

  return (
    <div className="gene-chips">
      <span className="gene-chips-label">Genes:</span>
      <div className="gene-chips-list">
        {variants.map((v) => (
          <div key={v.id} className="gene-chip-wrapper">
            <button
              type="button"
              className={`gene-chip ${v.selected ? 'selected' : ''}`}
              onClick={() => onToggle(v.id)}
            >
              {v.name}
            </button>
            {v.selected && (
              <>
                <button
                  type="button"
                  className="gene-chip-phenotype"
                  onClick={(e) => {
                    e.stopPropagation();
                    setOpenPhenotype(openPhenotype === v.id ? null : v.id);
                  }}
                >
                  {v.phenotype}
                </button>
                {openPhenotype === v.id && (
                  <div className="gene-phenotype-dropdown">
                    {PHENOTYPES.map((p) => (
                      <button
                        key={p}
                        type="button"
                        className={p === v.phenotype ? 'active' : ''}
                        onClick={(e) => {
                          e.stopPropagation();
                          onPhenotypeChange(v.id, p);
                          setOpenPhenotype(null);
                        }}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
