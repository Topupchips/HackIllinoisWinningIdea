import Structure2D from './Structure2D';
import GeneVisual from './GeneVisual';
import './CompoundGeneDiagram.css';

interface Medication {
  id: string;
  name: string;
  smiles: string;
  formula: string;
  compoundType: string;
}

interface GeneticVariant {
  id: string;
  name: string;
  enzyme: string;
  phenotype: string;
  selected: boolean;
}

interface CompoundGeneDiagramProps {
  medications: Medication[];
  variants: GeneticVariant[];
}

export default function CompoundGeneDiagram({ medications, variants }: CompoundGeneDiagramProps) {
  const selectedVariants = variants.filter((v) => v.selected);
  const hasData = medications.length > 0 && selectedVariants.length > 0;

  if (!hasData) {
    return (
      <div className="compound-gene-diagram empty">
        <p>Add compounds and select genes in the Gene Selector to see the interaction map.</p>
      </div>
    );
  }

  return (
    <div className="compound-gene-diagram">
      <div className="diagram-header">
        <span>Compounds</span>
        <span className="diagram-arrow">→</span>
        <span>Metabolizing Enzymes</span>
      </div>
      <div className="diagram-content">
        <div className="compounds-column">
          {medications.map((m) => (
            <div key={m.id} className="compound-node">
              <div className="compound-structure">
                <Structure2D smiles={m.smiles} name={m.name} size={80} />
              </div>
              <span className="compound-name">{m.name}</span>
            </div>
          ))}
        </div>
        <div className="diagram-bridge">
          <div className="bridge-lines" />
        </div>
        <div className="genes-column">
          {selectedVariants.map((v) => (
            <GeneVisual
              key={v.id}
              name={v.name}
              phenotype={v.phenotype}
              enzyme={v.enzyme}
              selected={v.selected}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
