/**
 * Data types for drug interaction ML pipeline.
 * See docs/DATA_AND_MODEL_SPEC.md for full specification.
 */

export type DDISeverity = 'major' | 'moderate' | 'minor';

export type DDIEvidenceLevel = 'known' | 'predicted' | 'novel';

export type InteractionType =
  | 'metabolic_competition'
  | 'enzyme_inhibition'
  | 'enzyme_induction'
  | 'pharmacodynamic'
  | 'unknown';

export interface DDIRecord {
  drug_a_id: string;
  drug_b_id: string;
  drug_a_smiles?: string;
  drug_b_smiles?: string;
  drug_a_name?: string;
  drug_b_name?: string;
  interaction_type: InteractionType;
  severity: DDISeverity;
  evidence_level: DDIEvidenceLevel;
  clinical_evidence?: string;
}

export type CYPEnzyme =
  | 'CYP1A2'
  | 'CYP2C19'
  | 'CYP2C9'
  | 'CYP2D6'
  | 'CYP2E1'
  | 'CYP3A4';

export type DrugGeneRelationship = 'substrate' | 'inhibitor' | 'inducer';

export interface DrugGeneRecord {
  drug_id: string;
  drug_name?: string;
  smiles?: string;
  gene: CYPEnzyme;
  relationship: DrugGeneRelationship;
  phenotype_impact?: {
    poor?: string;
    intermediate?: string;
    extensive?: string;
    ultrarapid?: string;
  };
}

export interface CYP450SubstrateRecord {
  chemical_name: string;
  smiles: string;
  label: 0 | 1; // 1 = substrate, 0 = non-substrate
  data_sources?: string;
}

export interface DDIPrediction {
  confidence: number;
  severity: DDISeverity;
  known: boolean;
  mechanism?: string;
  tanimoto_similarity?: number;
}

export interface CYPSubstratePrediction {
  enzyme: CYPEnzyme;
  is_substrate: boolean;
  confidence: number;
}
