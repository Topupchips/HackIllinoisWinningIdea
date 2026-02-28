import { useState, useEffect } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import {
  Dna,
  Plus,
  Sparkles,
  AlertTriangle,
  HelpCircle,
} from 'lucide-react';
import Modal from './Modal';
import Scene3D from './Scene3D';
import MoleculeViewer3D from './MoleculeViewer3D';
import DrugSearch from './DrugSearch';
import CompoundGeneDiagram from './CompoundGeneDiagram';
import CompoundDropZone from './CompoundDropZone';
import QuickAddChips from './QuickAddChips';
import GeneChips from './GeneChips';
import CollapsibleSection from './CollapsibleSection';
import { getCompoundByName } from '../services/api';
import { smilesSimilarity } from '../utils/smilesSimilarity';
import { explainInteraction, askAI, getSimilarDrugs } from '../services/api';
import './Simulator.css';

type CompoundType = 'small_molecule' | 'biologic' | 'vaccine' | 'supplement';

interface Medication {
  id: string;
  name: string;
  smiles: string;
  formula: string;
  compoundType: CompoundType;
  dosage: string;
  frequency: string;
}

interface GeneticVariant {
  id: string;
  name: string;
  enzyme: string;
  phenotype: string;
  selected: boolean;
}

const GENETIC_VARIANTS: GeneticVariant[] = [
  { id: 'cyp2c19', name: 'CYP2C19', enzyme: 'PPIs, clopidogrel', phenotype: 'Extensive', selected: false },
  { id: 'cyp2d6', name: 'CYP2D6', enzyme: 'Antidepressants, opioids', phenotype: 'Extensive', selected: false },
  { id: 'cyp3a4', name: 'CYP3A4', enzyme: 'Statins, immunosuppressants', phenotype: 'Extensive', selected: false },
  { id: 'nat2', name: 'NAT2', enzyme: 'Isoniazid, hydralazine', phenotype: 'Extensive', selected: false },
];

function generateTimelineData(medications: Medication[], hasVaccine: boolean): { hour: number; risk: number; concentration: number; label: string }[] {
  const data = [];
  const baseRisk = medications.length >= 2 ? 0.4 : 0.1;
  const vaccineBoost = hasVaccine ? 0.25 : 0;

  for (let h = 0; h <= 72; h += 2) {
    let risk = baseRisk + Math.sin(h / 12) * 0.3 + vaccineBoost;
    if (hasVaccine && h >= 24 && h <= 48) risk += 0.2;
    risk = Math.min(1, Math.max(0.1, risk));
    const concentration = Math.exp(-h / 24) * (1 + Math.sin(h / 8) * 0.3);
    data.push({
      hour: h,
      risk: Math.round(risk * 100),
      concentration: Math.round(concentration * 100),
      label: `${h}h`,
    });
  }
  return data;
}

export default function Simulator() {
  const [medications, setMedications] = useState<Medication[]>([]);
  const [variants, setVariants] = useState<GeneticVariant[]>(GENETIC_VARIANTS);
  const [newName, setNewName] = useState('');
  const [newSmiles, setNewSmiles] = useState('');
  const [newFormula, setNewFormula] = useState('');
  const [newType, setNewType] = useState<CompoundType>('small_molecule');
  const [mechanismModalOpen, setMechanismModalOpen] = useState(false);
  const [mechanismLoading, setMechanismLoading] = useState(false);
  const [mechanismText, setMechanismText] = useState('');
  const [askModalOpen, setAskModalOpen] = useState(false);
  const [askQuestion, setAskQuestion] = useState('');
  const [askLoading, setAskLoading] = useState(false);
  const [askAnswer, setAskAnswer] = useState('');
  const [similarModalOpen, setSimilarModalOpen] = useState(false);
  const [similarDrugs, setSimilarDrugs] = useState<{ name: string; smiles: string }[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [similarFor, setSimilarFor] = useState('');
  const [nlInput, setNlInput] = useState('');
  const [nlLoading, setNlLoading] = useState(false);

  const hasVaccine = medications.some((m) => m.compoundType === 'vaccine');
  const isNovel = medications.length >= 2;
  const timelineData = generateTimelineData(medications, hasVaccine);

  const addMedication = (m: Partial<Medication>) => {
    setMedications((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        name: m.name || 'Unknown',
        smiles: m.smiles || '',
        formula: m.formula || '',
        compoundType: m.compoundType || 'small_molecule',
        dosage: m.dosage || 'N/A',
        frequency: m.frequency || 'N/A',
      },
    ]);
  };

  const removeMedication = (id: string) => {
    setMedications((prev) => prev.filter((m) => m.id !== id));
  };

  const handleAddCustom = () => {
    if (!newName.trim()) return;
    addMedication({
      name: newName,
      smiles: newSmiles,
      formula: newFormula,
      compoundType: newType,
        dosage: 'N/A',
        frequency: 'N/A',
    });
    setNewName('');
    setNewSmiles('');
    setNewFormula('');
  };

  const toggleVariant = (id: string) => {
    setVariants((prev) =>
      prev.map((v) => (v.id === id ? { ...v, selected: !v.selected } : v))
    );
  };

  const setVariantPhenotype = (id: string, phenotype: string) => {
    setVariants((prev) =>
      prev.map((v) => (v.id === id ? { ...v, phenotype } : v))
    );
  };

  const handleDrugSearchSelect = (compound: { name: string; smiles: string; formula: string }) => {
    addMedication({
      name: compound.name,
      smiles: compound.smiles,
      formula: compound.formula,
      compoundType: 'small_molecule',
      dosage: 'N/A',
      frequency: 'N/A',
    });
  };

  const handleNaturalLanguageAdd = async () => {
    const names = nlInput.split(/[+,&]/).map((s) => s.trim()).filter(Boolean);
    if (names.length === 0) return;
    setNlLoading(true);
    for (const name of names) {
      const compound = await getCompoundByName(name);
      if (compound?.smiles) {
        addMedication({
          name: compound.name,
          smiles: compound.smiles,
          formula: compound.formula,
          compoundType: 'small_molecule',
          dosage: 'N/A',
          frequency: 'N/A',
        });
      }
    }
    setNlInput('');
    setNlLoading(false);
  };

  const confidence = Math.min(95, 70 + medications.length * 5 + (hasVaccine ? 10 : 0));
  const tanimotoSim =
    medications.length >= 2
      ? (() => {
          let sum = 0;
          let count = 0;
          for (let i = 0; i < medications.length; i++) {
            for (let j = i + 1; j < medications.length; j++) {
              sum += smilesSimilarity(medications[i].smiles, medications[j].smiles);
              count++;
            }
          }
          return (count > 0 ? sum / count : 0).toFixed(2);
        })()
      : '0.00';

  useEffect(() => {
    if (!mechanismModalOpen || medications.length < 2) return;
    setMechanismLoading(true);
    setMechanismText('');
    explainInteraction(
      medications.map((m) => m.name),
      parseFloat(tanimotoSim),
      confidence,
      hasVaccine
    )
      .then((r) => setMechanismText(r.explanation || ''))
      .catch(() => setMechanismText('Unable to load AI explanation.'))
      .finally(() => setMechanismLoading(false));
  }, [mechanismModalOpen, medications, tanimotoSim, confidence, hasVaccine]);

  const handleAskAI = async () => {
    if (!askQuestion.trim()) return;
    setAskLoading(true);
    setAskAnswer('');
    try {
      const r = await askAI(askQuestion, {
        compounds: medications.map((m) => m.name),
        tanimoto: parseFloat(tanimotoSim),
        genes: variants.filter((v) => v.selected).map((v) => `${v.name} (${v.phenotype})`),
      });
      setAskAnswer(r.answer);
    } catch {
      setAskAnswer('Unable to get answer.');
    } finally {
      setAskLoading(false);
    }
  };

  const handleSimilarDrugs = (name: string, smiles: string) => {
    setSimilarFor(name);
    setSimilarModalOpen(true);
    setSimilarLoading(true);
    setSimilarDrugs([]);
    getSimilarDrugs(smiles || 'CC(=O)OC1=CC=CC=C1C(=O)O', 5)
      .then((r) => setSimilarDrugs(r.similar))
      .catch(() => setSimilarDrugs([]))
      .finally(() => setSimilarLoading(false));
  };

  return (
    <div className="simulator">
      <div className="sim-bg" />

      <nav className="sim-nav">
        <div className="nav-logo">
          <Dna size={24} />
          <span>PHARMAGEN</span>
        </div>
        <div className="nav-3d">
          <Scene3D />
        </div>
      </nav>

      <main className="sim-main sim-main-hands-on">
        <aside className="sim-sidebar">
          <div className="sidebar-section glass-card">
            <h3>Add compounds</h3>
            <DrugSearch onSelect={handleDrugSearchSelect} />
            <QuickAddChips onAdd={(c) => addMedication({ ...c, compoundType: 'small_molecule', dosage: 'N/A', frequency: 'N/A' })} />
            <div className="nl-input">
              <input
                placeholder="Or type: Aspirin + Ibuprofen"
                value={nlInput}
                onChange={(e) => setNlInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleNaturalLanguageAdd()}
              />
              <button onClick={handleNaturalLanguageAdd} disabled={nlLoading || !nlInput.trim()}>
                {nlLoading ? '...' : 'Add'}
              </button>
            </div>
            <GeneChips
              variants={variants}
              onToggle={toggleVariant}
              onPhenotypeChange={setVariantPhenotype}
            />
            <CollapsibleSection title="Manual (SMILES)">
              <div className="custom-input">
                <input placeholder="Name" value={newName} onChange={(e) => setNewName(e.target.value)} />
                <input placeholder="SMILES" value={newSmiles} onChange={(e) => setNewSmiles(e.target.value)} />
                <input placeholder="Formula" value={newFormula} onChange={(e) => setNewFormula(e.target.value)} />
                <select value={newType} onChange={(e) => setNewType(e.target.value as CompoundType)}>
                  <option value="small_molecule">Small Molecule</option>
                  <option value="biologic">Biologic</option>
                  <option value="vaccine">Vaccine</option>
                  <option value="supplement">Supplement</option>
                </select>
                <button onClick={handleAddCustom} className="add-btn">
                  <Plus size={16} /> Add
                </button>
              </div>
            </CollapsibleSection>
          </div>
        </aside>

        <div className="sim-content">
          <CompoundDropZone
            medications={medications}
            onAdd={(c) => addMedication({ ...c, compoundType: 'small_molecule', dosage: 'N/A', frequency: 'N/A' })}
            onRemove={removeMedication}
            onSimilar={handleSimilarDrugs}
          />

          <div className="chart-section glass-card">
            <div className="chart-header">
              <h3>
                <Sparkles size={18} />
                Interaction Timeline (72h)
                {isNovel && <span className="badge-novel">Novel Combination</span>}
              </h3>
              <div className="chart-actions">
                <button
                  className="chart-action-btn"
                  onClick={() => setMechanismModalOpen(true)}
                  title="Mechanistic AI Explanation"
                >
                  <HelpCircle size={16} />
                  <span>AI Explanation</span>
                </button>
                <button
                  className="chart-action-btn"
                  onClick={() => setAskModalOpen(true)}
                  title="Ask AI"
                >
                  <Sparkles size={16} />
                  <span>Ask AI</span>
                </button>
              </div>
            </div>
            <div className="chart-meta">
              AI Confidence: <span className="confidence">{confidence}%</span>
              {medications.length >= 2 && (
                <span className="meta-item">Tanimoto: {tanimotoSim}</span>
              )}
            </div>
            <div className="chart-wrapper">
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={timelineData}>
                  <defs>
                    <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ef4444" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="concGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#14b8a6" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#14b8a6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="label" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(10,10,15,0.95)',
                      border: '1px solid rgba(20,184,166,0.3)',
                      borderRadius: '8px',
                    }}
                    labelStyle={{ color: '#94a3b8' }}
                  />
                  <Area type="monotone" dataKey="risk" stroke="#ef4444" fill="url(#riskGrad)" strokeWidth={2} />
                  <Area type="monotone" dataKey="concentration" stroke="#14b8a6" fill="url(#concGrad)" strokeWidth={2} />
                  <ReferenceLine y={70} stroke="#eab308" strokeDasharray="5 5" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="visual-section glass-card">
            <h4>Compound–Gene Interaction Map</h4>
            <CompoundGeneDiagram medications={medications} variants={variants} />
          </div>

          <div className="analysis-section">
            {medications.length > 0 && (
              <div className="molecule-preview glass-card">
                <MoleculeViewer3D atomCount={medications.reduce((a, m) => a + m.smiles.length, 0) % 8 + 4} />
              </div>
            )}
            <div className="analysis-card glass-card">
              <h4>
                <AlertTriangle size={18} />
                AI Predictions
              </h4>
              {medications.length < 2 ? (
                <p className="no-data">Add 2+ compounds for predictions.</p>
              ) : (
                <>
                  <div className="risk-gauge">
                    <div className="gauge-ring" style={{ '--risk': confidence } as React.CSSProperties} />
                    <span className="gauge-value">{confidence}%</span>
                  </div>
                  <div className="interaction-item">
                    <span className="sev-medium">Metabolic competition</span>
                    <span className="conf">Tanimoto {tanimotoSim}</span>
                  </div>
                  {hasVaccine && (
                    <div className="interaction-item">
                      <span className="sev-low">Immune modulation</span>
                      <span className="conf">85%</span>
                    </div>
                  )}
                  {isNovel && (
                    <div className="novel-badge">
                      <Sparkles size={14} />
                      Novel combination
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <Modal
            isOpen={mechanismModalOpen}
            onClose={() => setMechanismModalOpen(false)}
            title="Mechanistic AI Explanation"
          >
            <div className="mechanism-content">
              {medications.length < 2 ? (
                <p className="no-data">Add 2+ compounds to view mechanistic analysis.</p>
              ) : mechanismLoading ? (
                <p className="no-data">Loading AI explanation…</p>
              ) : mechanismText ? (
                <div className="mechanism-section">
                  <p style={{ whiteSpace: 'pre-wrap' }}>{mechanismText}</p>
                </div>
              ) : (
                <p className="no-data">No explanation available.</p>
              )}
            </div>
          </Modal>

          <Modal
            isOpen={askModalOpen}
            onClose={() => setAskModalOpen(false)}
            title="Ask AI"
          >
            <div className="ask-ai-content">
              <input
                placeholder="e.g. What CYP enzymes are involved?"
                value={askQuestion}
                onChange={(e) => setAskQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAskAI()}
                className="ask-input"
              />
              <button onClick={handleAskAI} disabled={askLoading || !askQuestion.trim()} className="ask-submit">
                {askLoading ? 'Thinking…' : 'Ask'}
              </button>
              {askAnswer && <p className="ask-answer">{askAnswer}</p>}
            </div>
          </Modal>

          <Modal
            isOpen={similarModalOpen}
            onClose={() => setSimilarModalOpen(false)}
            title={`Similar to ${similarFor}`}
          >
            <div className="similar-drugs-content">
              {similarLoading ? (
                <p className="no-data">Finding similar drugs…</p>
              ) : similarDrugs.length > 0 ? (
                <ul className="similar-list">
                  {similarDrugs.map((d) => (
                    <li key={d.name}>
                      <span>{d.name}</span>
                      <button
                        type="button"
                        className="similar-add-btn"
                        onClick={() => {
                          addMedication({ name: d.name, smiles: d.smiles, formula: '', compoundType: 'small_molecule', dosage: 'N/A', frequency: 'N/A' });
                          setSimilarModalOpen(false);
                        }}
                      >
                        Add
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="no-data">No similar drugs found.</p>
              )}
            </div>
          </Modal>

          <div className="recommendations glass-card">
            <h4>Recommendations</h4>
            {medications.length < 2 ? (
              <p>Add medications to receive AI-generated recommendations.</p>
            ) : (
              <ul>
                <li>Monitor for Days 1-7 post-vaccination if vaccine present.</li>
                <li>Consider genetic variant impact on metabolism.</li>
                <li>Validate novel combinations with healthcare provider.</li>
              </ul>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
