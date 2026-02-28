const PUBCHEM_BASE = 'https://pubchem.ncbi.nlm.nih.gov/rest/pug';

export interface PubChemCompound {
  name: string;
  smiles: string;
  formula: string;
  cid?: number;
}

export async function searchDrugs(query: string): Promise<string[]> {
  if (!query.trim()) return [];
  try {
    const res = await fetch(
      `https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/${encodeURIComponent(query)}/json`
    );
    const data = await res.json();
    const terms = data?.dictionary_terms?.compound;
    return Array.isArray(terms) ? terms.slice(0, 8) : [];
  } catch {
    return [];
  }
}

export async function fetchCompoundByName(name: string): Promise<PubChemCompound | null> {
  try {
    const res = await fetch(
      `${PUBCHEM_BASE}/compound/name/${encodeURIComponent(name)}/property/MolecularFormula,SMILES,IsomericSMILES/JSON`
    );
    const data = await res.json();
    const props = data?.PropertyTable?.Properties?.[0];
    if (!props) return null;
    return {
      name,
      smiles: props.IsomericSMILES || props.SMILES || '',
      formula: props.MolecularFormula || '',
      cid: props.CID,
    };
  } catch {
    return null;
  }
}

export function getStructureImageUrl(smiles: string, size = 150): string {
  const encoded = encodeURIComponent(smiles);
  return `${PUBCHEM_BASE}/compound/smiles/${encoded}/PNG?image_size=${size}x${size}`;
}
