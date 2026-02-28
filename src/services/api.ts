/**
 * Pharmacogen Web API client
 * Set VITE_API_URL to your Modal deployment (e.g. https://your-workspace--pharmacogen-api.modal.run)
 */

const BASE = import.meta.env.VITE_API_URL || '';

async function get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(path, BASE);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: object): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// --- Health ---

export async function healthCheck(): Promise<{ status: string; api: string; version: string }> {
  if (!BASE) return { status: 'offline', api: 'pharmacogen', version: '1.0.0' };
  return get('/v1/health');
}

// --- Drugs ---

export interface DrugSearchResponse {
  query: string;
  results: string[];
  total?: number;
  limit?: number;
  offset?: number;
}

export async function searchDrugs(query: string): Promise<DrugSearchResponse> {
  if (BASE) {
    try {
      return await get<DrugSearchResponse>('/v1/drugs/search', { q: query });
    } catch {
      return { query, results: [] };
    }
  }
  try {
    const r = await fetch(`https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/${encodeURIComponent(query)}/json`);
    const data = await r.json();
    const terms = data?.dictionary_terms?.compound;
    return { query, results: Array.isArray(terms) ? terms.slice(0, 10) : [] };
  } catch {
    return { query, results: [] };
  }
}

export interface CompoundResponse {
  name: string;
  smiles: string;
  formula: string;
  cid?: number;
}

export interface BatchCompoundsResponse {
  compounds: CompoundResponse[];
  requested: number;
  found: number;
}

export async function getCompoundByName(name: string): Promise<CompoundResponse | null> {
  if (BASE) {
    try {
      return await get<CompoundResponse>(`/v1/drugs/name/${encodeURIComponent(name)}`);
    } catch {
      return null;
    }
  }
  try {
    const r = await fetch(
      `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/${encodeURIComponent(name)}/property/MolecularFormula,SMILES,IsomericSMILES/JSON`
    );
    const data = await r.json();
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

export async function batchCompounds(names: string[]): Promise<BatchCompoundsResponse> {
  if (!BASE) return { compounds: [], requested: names.length, found: 0 };
  return post<BatchCompoundsResponse>('/v1/drugs/batch', { names });
}

export interface SimilarDrug {
  name: string;
  smiles: string;
}

export interface SimilarDrugsResponse {
  similar: SimilarDrug[];
  source: string;
}

export async function getSimilarDrugs(smiles: string, limit = 5): Promise<SimilarDrugsResponse> {
  if (!BASE) return { similar: [], source: 'offline' };
  return get<SimilarDrugsResponse>('/v1/drugs/similar', { smiles, limit });
}

// --- Interactions ---

export interface ExplainResponse {
  explanation: string;
  source: 'openai' | 'fallback';
  error?: string;
}

export async function explainInteraction(
  compounds: string[],
  tanimoto: number,
  confidence: number,
  hasVaccine: boolean
): Promise<ExplainResponse> {
  if (!BASE) return { explanation: '', source: 'fallback' };
  return post<ExplainResponse>('/v1/interactions/explain', {
    compounds,
    tanimoto,
    confidence,
    has_vaccine: hasVaccine,
  });
}

export interface AskResponse {
  answer: string;
}

export async function askAI(
  question: string,
  context: { compounds?: string[]; tanimoto?: number; genes?: string[] }
): Promise<AskResponse> {
  if (!BASE) {
    return { answer: 'API not configured. Set VITE_API_URL to your Modal deployment.' };
  }
  return post<AskResponse>('/v1/interactions/ask', { question, context });
}

export interface PredictResponse {
  compounds: string[];
  tanimoto_avg: number;
  confidence: number;
  has_vaccine: boolean;
  pairs: { drugs: string[]; tanimoto: number }[];
}

export interface TimelinePoint {
  hour: number;
  risk: number;
  concentration: number;
  label: string;
}

export interface TimelineResponse {
  timeline: TimelinePoint[];
}

export async function getTimeline(
  compoundCount: number,
  hasVaccine: boolean,
  tanimotoAvg = 0.5
): Promise<TimelineResponse> {
  if (!BASE) return { timeline: [] };
  return get<TimelineResponse>('/v1/interactions/timeline', {
    compound_count: compoundCount,
    has_vaccine: hasVaccine,
    tanimoto_avg: tanimotoAvg,
  });
}

export async function predictInteraction(
  compounds: string[],
  smilesList: string[],
  hasVaccine: boolean
): Promise<PredictResponse> {
  if (!BASE) {
    return {
      compounds,
      tanimoto_avg: 0,
      confidence: 70,
      has_vaccine: hasVaccine,
      pairs: [],
    };
  }
  return post<PredictResponse>('/v1/interactions/predict', {
    compounds,
    smiles_list: smilesList,
    has_vaccine: hasVaccine,
  });
}
