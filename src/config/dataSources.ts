/**
 * Data source URLs and configuration for ML pipeline.
 * See docs/DATA_AND_MODEL_SPEC.md for full specification.
 */

export const DATA_SOURCES = {
  // NCATS Inxight - Drug–drug interactions (download zip, extract frdb-ddi.tsv)
  NCATS_FRDB: 'https://drugs.ncats.io/downloads-public/frdb-v2024-12-30.zip',

  // Curated CYP450 - Substrate classification per enzyme
  // Dataset: https://figshare.com/articles/dataset/.../26630515
  // Download CSV files (CYP1A2, CYP2C9, CYP2C19, CYP2D6, CYP2E1, CYP3A4) from Figshare
  CYP450_DATASET_URL: 'https://figshare.com/articles/dataset/Comprehensively-Curated_Dataset_of_CYP450_Interactions_Enhancing_Predictive_Models_for_Drug_Metabolism/26630515',

  // APIs
  PUBCHEM_BASE: 'https://pubchem.ncbi.nlm.nih.gov/rest/pug',
  PHARMGKB_BASE: 'https://api.pharmgkb.org',
  CPIC_BASE: 'https://api.cpicpgx.org',
} as const;

export const CYP_ENZYMES = [
  'CYP1A2',
  'CYP2C9',
  'CYP2C19',
  'CYP2D6',
  'CYP2E1',
  'CYP3A4',
] as const;
