/**
 * Deterministic similarity from SMILES (placeholder until RDKit fingerprints).
 * Uses character 3-gram overlap as a proxy for structural similarity.
 * For production: use RDKit.js Morgan fingerprints + Tanimoto.
 */

function getNGrams(s: string, n: number): Set<string> {
  const grams = new Set<string>();
  for (let i = 0; i <= s.length - n; i++) {
    grams.add(s.slice(i, i + n));
  }
  return grams;
}

export function smilesSimilarity(smilesA: string, smilesB: string): number {
  if (!smilesA || !smilesB) return 0;
  const a = getNGrams(smilesA, 3);
  const b = getNGrams(smilesB, 3);
  let intersection = 0;
  for (const g of a) {
    if (b.has(g)) intersection++;
  }
  const union = a.size + b.size - intersection;
  return union === 0 ? 0 : intersection / union;
}
