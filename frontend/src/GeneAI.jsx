import { useState, useEffect, useRef } from "react";
import * as THREE from "three";

const GENES = ["CYP2D6","CYP2C19","CYP2C9","CYP3A5","DPYD","TPMT","NUDT15","UGT1A1","SLCO1B1","HLA-B","HLA-A","ABCG2","G6PD","CACNA1S","RYR1","CYP2B6","VKORC1"];
const PHENOTYPES = ["Poor Metabolizer","Intermediate Metabolizer","Normal Metabolizer","Rapid Metabolizer","Ultrarapid Metabolizer"];
const SAMPLE_DRUGS = ["codeine","warfarin","clopidogrel","simvastatin","tamoxifen","omeprazole","abacavir","carbamazepine","metoprolol","amitriptyline","fluorouracil","azathioprine","allopurinol","tramadol","ibuprofen"];

const API_BASE = "http://localhost:8000";

function DNAHelix({ riskLevel }) {
  const mountRef = useRef(null);
  const frameRef = useRef(null);

  useEffect(() => {
    if (!mountRef.current) return;
    const c = mountRef.current;
    const w = c.clientWidth, h = c.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0f0f0);

    const camera = new THREE.PerspectiveCamera(28, w / h, 0.1, 200);
    camera.position.set(4, 0.5, 11);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    c.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const d1 = new THREE.DirectionalLight(0xffffff, 1.4);
    d1.position.set(12, 18, 10);
    scene.add(d1);
    const d2 = new THREE.DirectionalLight(0xf0eaff, 0.5);
    d2.position.set(-10, -8, -6);
    scene.add(d2);
    const r1 = new THREE.PointLight(0xffffff, 0.5, 30);
    r1.position.set(-5, 10, 12);
    scene.add(r1);
    const r2 = new THREE.PointLight(0xfff8f0, 0.3, 25);
    r2.position.set(8, -8, 10);
    scene.add(r2);

    const group = new THREE.Group();
    group.rotation.z = -0.38;
    group.rotation.x = 0.1;
    scene.add(group);

    const g1 = new THREE.SphereGeometry(0.22, 14, 14);
    const g2 = new THREE.SphereGeometry(0.16, 10, 10);
    const g3 = new THREE.SphereGeometry(0.11, 8, 8);
    const g4 = new THREE.SphereGeometry(0.07, 6, 6);
    const g5 = new THREE.SphereGeometry(0.05, 5, 5);
    const gBond = new THREE.SphereGeometry(0.08, 6, 6);
    const geoms = [g1, g2, g2, g3, g3, g3, g4, g4, g4, g5];

    const m1 = () => new THREE.MeshPhysicalMaterial({ color: 0xe2e2e2, roughness: 0.25, metalness: 0.01, clearcoat: 0.6, clearcoatRoughness: 0.12 });
    const m2 = () => new THREE.MeshPhysicalMaterial({ color: 0xd4d4d4, roughness: 0.32, metalness: 0.02, clearcoat: 0.5, clearcoatRoughness: 0.18 });
    const m3 = () => new THREE.MeshPhysicalMaterial({ color: 0xcdcdcd, roughness: 0.38, metalness: 0.03, clearcoat: 0.4, clearcoatRoughness: 0.22 });
    const mats = [m1, m1, m2, m2, m3];

    const N = 140;   // more backbone points = denser along the spine
    const H = 20;
    const R = 2.1;
    const T = 5;

    for (let i = 0; i < N; i++) {
      const t = i / N;
      const y = t * H - H / 2;
      const a = t * Math.PI * 2 * T;

      const p1 = new THREE.Vector3(Math.cos(a) * R, y, Math.sin(a) * R);
      const p2 = new THREE.Vector3(Math.cos(a + Math.PI) * R, y, Math.sin(a + Math.PI) * R);

      // More molecules per point, tighter spread
      for (const p of [p1, p2]) {
        const count = 20 + Math.floor(Math.random() * 8);  // was 12-18, now 20-28
        for (let j = 0; j < count; j++) {
          const geom = geoms[Math.floor(Math.random() * geoms.length)];
          const matFn = mats[Math.floor(Math.random() * mats.length)];
          const spread = j < 3 ? 0 : 0.28;  // tighter spread (was 0.42)
          const mesh = new THREE.Mesh(geom, matFn());
          mesh.position.set(
            p.x + (Math.random() - 0.5) * spread,
            p.y + (Math.random() - 0.5) * spread * 0.6,
            p.z + (Math.random() - 0.5) * spread
          );
          group.add(mesh);
        }
      }

      // Denser bond rungs — every 2 steps instead of 3
      if (i % 2 === 0 && i > 0) {
        const steps = 14;  // more beads per rung (was 12)
        for (let s = 0; s <= steps; s++) {
          const f = s / steps;
          const pos = new THREE.Vector3().lerpVectors(p1, p2, f);
          const bond = new THREE.Mesh(gBond, m2());
          bond.position.copy(pos);
          group.add(bond);
          for (let e = 0; e < 4; e++) {  // was 3 extra per bead
            const ex = new THREE.Mesh(g5, m3());
            ex.position.set(
              pos.x + (Math.random() - 0.5) * 0.12,
              pos.y + (Math.random() - 0.5) * 0.08,
              pos.z + (Math.random() - 0.5) * 0.12
            );
            group.add(ex);
          }
        }
      }
    }

    let time = 0;
    const animate = () => {
      frameRef.current = requestAnimationFrame(animate);
      time += 0.0012;
      group.rotation.y = time;
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const ww = c.clientWidth, hh = c.clientHeight;
      camera.aspect = ww / hh;
      camera.updateProjectionMatrix();
      renderer.setSize(ww, hh);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(frameRef.current);
      if (c.contains(renderer.domElement)) c.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, [riskLevel]);

  return <div ref={mountRef} style={{ width: "100%", height: "100%", position: "absolute", inset: 0 }} />;
}

function LiquidGlass({ children, style = {} }) {
  return (
    <div style={{
      position: "relative",
      borderRadius: "24px",
      background: "rgba(255, 255, 255, 0.06)",
      backdropFilter: "blur(12px) saturate(1.2)",
      WebkitBackdropFilter: "blur(12px) saturate(1.2)",
      border: "1px solid rgba(255, 255, 255, 0.22)",
      boxShadow: `
        0 2px 16px rgba(0, 0, 0, 0.06),
        0 1px 0 rgba(255, 255, 255, 0.45) inset
      `,
      overflow: "hidden",
      ...style
    }}>
      {children}
    </div>
  );
}

function ResultCard({ result, index }) {
  const isRisky = result.activity_level <= 0.5;
  const isCaution = result.activity_level > 0.5 && result.activity_level < 1.0;
  return (
    <div style={{
      padding: "20px 24px", borderBottom: "1px solid rgba(0,0,0,0.05)",
      animation: `fadeIn 0.4s ease ${index * 0.1}s both`
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            width: "36px", height: "36px", borderRadius: "50%",
            background: isRisky ? "#1a1a1a" : isCaution ? "#555" : "#bbb",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "13px", color: "#fff", fontWeight: "600",
            boxShadow: isRisky ? "0 3px 10px rgba(0,0,0,0.25)" : "none"
          }}>
            {result.activity_level.toFixed(1)}
          </div>
          <span style={{
            fontFamily: "'SF Mono', monospace", fontSize: "17px",
            fontWeight: "700", color: "#1a1a1a", letterSpacing: "0.5px"
          }}>
            {result.gene}
          </span>
        </div>
        <span style={{
          fontSize: "14px", color: "#777", background: "rgba(0,0,0,0.04)",
          padding: "5px 14px", borderRadius: "20px"
        }}>
          {result.medicine}
        </span>
      </div>
      <p style={{ margin: 0, fontSize: "15px", color: "#444", lineHeight: "1.8", paddingLeft: "48px" }}>
        {result.text}
      </p>
    </div>
  );
}

export default function GeneAI() {
  const [genes, setGenes] = useState([{ name: "", phenotype: "" }]);
  const [drug, setDrug] = useState("");
  const [drugSearch, setDrugSearch] = useState("");
  const [showDrugs, setShowDrugs] = useState(false);
  const [geneSearches, setGeneSearches] = useState([""]);
  const [showGenes, setShowGenes] = useState([false]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [riskLevel, setRiskLevel] = useState(null);

  const filtered = SAMPLE_DRUGS.filter(d => d.includes(drugSearch.toLowerCase())).slice(0, 6);
  const filteredGenes = (i) => GENES.filter(g => g.toLowerCase().includes((geneSearches[i] || "").toLowerCase())).slice(0, 8);

  const [showPhenotypes, setShowPhenotypes] = useState([false]);

  const addGene = () => { setGenes([...genes, { name: "", phenotype: "" }]); setGeneSearches([...geneSearches, ""]); setShowGenes([...showGenes, false]); setShowPhenotypes([...showPhenotypes, false]); };
  const removeGene = (i) => { setGenes(genes.filter((_, idx) => idx !== i)); setGeneSearches(geneSearches.filter((_, idx) => idx !== i)); setShowGenes(showGenes.filter((_, idx) => idx !== i)); setShowPhenotypes(showPhenotypes.filter((_, idx) => idx !== i)); };
  const updateGene = (i, f, v) => { const u = [...genes]; u[i] = { ...u[i], [f]: v }; setGenes(u); };
  const setShowGene = (i, val) => { const u = [...showGenes]; u[i] = val; setShowGenes(u); };
  const setGeneSearch = (i, val) => { const u = [...geneSearches]; u[i] = val; setGeneSearches(u); };
  const setShowPhenotype = (i, val) => { const u = [...showPhenotypes]; u[i] = val; setShowPhenotypes(u); };

  const analyze = async () => {
    setLoading(true); setError(null); setResults(null); setRiskLevel(null);
    const effectiveDrug = drug || drugSearch.trim();
    const valid = genes.filter(g => g.name && g.phenotype);
    if (!valid.length || !effectiveDrug) {
      setError("Select at least one gene with phenotype and a drug.");
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          genes: valid.map(g => ({ name: g.name, phenotype: g.phenotype })),
          drug: effectiveDrug
        })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `API error ${response.status}`);
      }

      const data = await response.json();
      // API returns a flat array: [{gene, activity_level, medicine, text}, ...]
      setResults(data);
      const min = Math.min(...data.map(r => r.activity_level));
      setRiskLevel(min <= 0 ? "danger" : min <= 0.5 ? "caution" : "safe");
    } catch (e) {
      setError(e.message || "Failed to reach API. Is the server running on port 8000?");
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setGenes([{ name: "", phenotype: "" }]); setDrug(""); setDrugSearch(""); setResults(null); setError(null); setRiskLevel(null); };

  const inp = {
    width: "100%", padding: "12px 16px", borderRadius: "16px",
    background: "rgba(255,255,255,0.6)", border: "1px solid rgba(0,0,0,0.07)",
    color: "#1a1a1a", fontSize: "15px", outline: "none", boxSizing: "border-box",
    boxShadow: "inset 0 1px 3px rgba(0,0,0,0.03)"
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f0f0f0", fontFamily: "'Inter','Helvetica Neue',sans-serif", position: "relative", overflow: "hidden" }}>
      <style>{`
        @keyframes fadeIn { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
        select { appearance:none; -webkit-appearance:none; background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M3 5l3 3 3-3' stroke='%23999' fill='none' stroke-width='1.5'/%3E%3C/svg%3E"); background-repeat:no-repeat; background-position:right 14px center; }
        select option { background:#fff; color:#1a1a1a; }
        ::placeholder { color:#aaa; }
      `}</style>

      <DNAHelix riskLevel={riskLevel} />

      {/* Header */}
      <div style={{ position: "fixed", top: 0, left: 0, right: 0, zIndex: 100, padding: "28px 44px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: "20px", fontWeight: "600", color: "#1a1a1a", letterSpacing: "-0.3px" }}>GeneAI</span>
        <span style={{ fontSize: "14px", color: "#999" }}>2026</span>
      </div>

      {/* How it works */}
      <LiquidGlass style={{ position: "fixed", left: "44px", top: "50%", transform: "translateY(-50%)", width: "360px", zIndex: 50 }}>
        <div style={{ padding: "28px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <span style={{ fontSize: "18px", fontWeight: "700", color: "#1a1a1a" }}>How it works</span>
            <a href={`${API_BASE}/docs`} target="_blank" rel="noopener noreferrer" style={{
              width: "38px", height: "38px", borderRadius: "50%", background: "#1a1a1a",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#fff", fontSize: "20px", fontWeight: "300", textDecoration: "none",
              boxShadow: "0 4px 14px rgba(0,0,0,0.2)"
            }}>+</a>
          </div>
          <p style={{ margin: 0, fontSize: "15px", color: "#555", lineHeight: "1.8" }}>
            Understanding your drug-gene interactions is easy. Select your genetic profile, choose a medication, and receive personalized safety recommendations.
          </p>
        </div>
      </LiquidGlass>

      {/* Analyze Risk */}
      <LiquidGlass style={{ position: "fixed", right: "44px", top: "100px", width: "360px", zIndex: 50, overflow: "visible" }}>
        <div style={{ padding: "28px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "22px" }}>
            <span style={{ fontSize: "18px", fontWeight: "700", color: "#1a1a1a" }}>Analyze Risk</span>
            <div onClick={analyze} style={{
              width: "38px", height: "38px", borderRadius: "50%",
              background: loading ? "#aaa" : "#1a1a1a",
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: loading ? "wait" : "pointer", color: "#fff", fontSize: "18px",
              boxShadow: "0 4px 14px rgba(0,0,0,0.2)", transition: "all 0.2s"
            }}>{loading ? "⟳" : "→"}</div>
          </div>

          {genes.map((g, i) => (
            <div key={i} style={{ display: "flex", gap: "8px", marginBottom: "10px" }}>
              <div style={{ position: "relative", flex: 1 }}>
                <input
                  type="text"
                  value={geneSearches[i] !== undefined ? geneSearches[i] : g.name}
                  onChange={e => { setGeneSearch(i, e.target.value); updateGene(i, "name", e.target.value); setShowGene(i, true); }}
                  onFocus={() => setShowGene(i, true)}
                  onBlur={() => setTimeout(() => setShowGene(i, false), 200)}
                  placeholder="Gene..."
                  style={{ ...inp, width: "100%" }}
                />
                {showGenes[i] && filteredGenes(i).length > 0 && (
                  <div style={{
                    position: "absolute", top: "100%", left: 0, right: 0, marginTop: "6px", zIndex: 200,
                    background: "rgba(245,245,247,0.92)", backdropFilter: "blur(60px) saturate(1.8)",
                    WebkitBackdropFilter: "blur(60px) saturate(1.8)",
                    border: "1px solid rgba(255,255,255,0.5)", borderRadius: "20px",
                    boxShadow: "0 8px 40px rgba(0,0,0,0.1)", overflow: "hidden", padding: "6px 0"
                  }}>
                    {filteredGenes(i).map(gn => (
                      <div key={gn} onMouseDown={e => { e.preventDefault(); updateGene(i, "name", gn); setGeneSearch(i, gn); setShowGene(i, false); }}
                        style={{ padding: "10px 20px", cursor: "pointer", fontSize: "15px", color: "#333", margin: "2px 6px", borderRadius: "12px" }}
                        onMouseEnter={e => e.target.style.background = "rgba(0,0,0,0.05)"}
                        onMouseLeave={e => e.target.style.background = "transparent"}>
                        {gn}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div style={{ position: "relative", flex: 1 }}>
                <div onClick={() => setShowPhenotype(i, !showPhenotypes[i])}
                  onBlur={() => setTimeout(() => setShowPhenotype(i, false), 200)}
                  tabIndex={0}
                  style={{ ...inp, width: "100%", cursor: "pointer", color: g.phenotype ? "#1a1a1a" : "#aaa", userSelect: "none" }}>
                  {g.phenotype || "Phenotype..."}
                </div>
                {showPhenotypes[i] && (
                  <div style={{
                    position: "absolute", top: "100%", left: 0, right: 0, marginTop: "6px", zIndex: 200,
                    background: "rgba(245,245,247,0.92)", backdropFilter: "blur(60px) saturate(1.8)",
                    WebkitBackdropFilter: "blur(60px) saturate(1.8)",
                    border: "1px solid rgba(255,255,255,0.5)", borderRadius: "20px",
                    boxShadow: "0 8px 40px rgba(0,0,0,0.1)", overflow: "hidden", padding: "6px 0"
                  }}>
                    {PHENOTYPES.map(p => (
                      <div key={p} onMouseDown={e => { e.preventDefault(); updateGene(i, "phenotype", p); setShowPhenotype(i, false); }}
                        style={{ padding: "10px 20px", cursor: "pointer", fontSize: "15px", color: "#333", margin: "2px 6px", borderRadius: "12px" }}
                        onMouseEnter={e => e.target.style.background = "rgba(0,0,0,0.05)"}
                        onMouseLeave={e => e.target.style.background = "transparent"}>
                        {p}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {genes.length > 1 && (
                <button onClick={() => removeGene(i)} style={{
                  background: "rgba(255,255,255,0.5)", border: "1px solid rgba(0,0,0,0.07)",
                  borderRadius: "14px", color: "#999", cursor: "pointer", padding: "0 10px", fontSize: "16px"
                }}>×</button>
              )}
            </div>
          ))}
          <button onClick={addGene} style={{ background: "none", border: "none", color: "#999", fontSize: "14px", cursor: "pointer", padding: "6px 0", marginBottom: "16px" }}>
            + add another gene
          </button>

          <div style={{ position: "relative" }}>
            <input type="text" value={drugSearch || drug}
              onChange={e => { setDrugSearch(e.target.value); setDrug(""); setShowDrugs(true); }}
              onFocus={() => { if (drugSearch) setShowDrugs(true); }}
              onBlur={() => setTimeout(() => setShowDrugs(false), 300)}
              placeholder="Type drug name..."
              style={inp} />
            {showDrugs && drugSearch && !drug && filtered.length > 0 && (
              <div style={{
                position: "absolute", top: "100%", left: 0, right: 0,
                marginTop: "6px", zIndex: 100,
                background: "rgba(245, 245, 247, 0.92)",
                backdropFilter: "blur(60px) saturate(1.8)",
                WebkitBackdropFilter: "blur(60px) saturate(1.8)",
                border: "1px solid rgba(255,255,255,0.5)",
                borderRadius: "20px",
                boxShadow: "0 8px 40px rgba(0,0,0,0.1)",
                overflow: "hidden",
                padding: "6px 0"
              }}>
                {filtered.map(d => (
                  <div key={d}
                    onMouseDown={e => {
                      e.preventDefault();
                      setDrug(d);
                      setDrugSearch(d);
                      setShowDrugs(false);
                    }}
                    style={{
                      padding: "12px 20px", cursor: "pointer", fontSize: "15px",
                      color: "#333", transition: "all 0.15s",
                      margin: "2px 6px", borderRadius: "12px"
                    }}
                    onMouseEnter={e => e.target.style.background = "rgba(0,0,0,0.05)"}
                    onMouseLeave={e => e.target.style.background = "transparent"}>
                    {d}
                  </div>
                ))}
              </div>
            )}
          </div>
          {error && <p style={{ margin: "14px 0 0", fontSize: "14px", color: "#cc4444" }}>{error}</p>}
        </div>
      </LiquidGlass>

      {/* Results */}
      {results && (
        <LiquidGlass style={{ position: "fixed", right: "44px", bottom: "44px", width: "420px", maxHeight: "50vh", overflowY: "auto", zIndex: 50 }}>
          <div>
            <div style={{ padding: "20px 24px", borderBottom: "1px solid rgba(0,0,0,0.06)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <span style={{ fontSize: "18px", fontWeight: "700", color: "#1a1a1a" }}>Results</span>
                <span style={{
                  fontSize: "12px", fontWeight: "600", textTransform: "uppercase", letterSpacing: "1px",
                  color: riskLevel === "danger" ? "#cc2244" : riskLevel === "caution" ? "#aa7700" : "#228844",
                  background: riskLevel === "danger" ? "rgba(204,34,68,0.08)" : riskLevel === "caution" ? "rgba(170,119,0,0.08)" : "rgba(34,136,68,0.08)",
                  padding: "5px 14px", borderRadius: "20px"
                }}>
                  {riskLevel === "danger" ? "High Risk" : riskLevel === "caution" ? "Moderate" : "Low Risk"}
                </span>
              </div>
              <div onClick={reset} style={{
                width: "34px", height: "34px", borderRadius: "50%", background: "rgba(0,0,0,0.05)",
                display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", fontSize: "16px", color: "#999"
              }}>×</div>
            </div>
            {results.map((r, i) => <ResultCard key={i} result={r} index={i} />)}
            <div style={{ padding: "16px 24px", fontSize: "12px", color: "#aaa", borderTop: "1px solid rgba(0,0,0,0.04)", lineHeight: "1.7" }}>
              CPIC v1.54.0 · Stanford/NIH · CC0 License<br />For educational purposes only. Consult a healthcare professional.
            </div>
          </div>
        </LiquidGlass>
      )}

      {/* Bottom branding */}
      <div style={{ position: "fixed", bottom: "44px", left: "44px", zIndex: 50 }}>
        <div style={{ fontSize: "58px", fontWeight: "800", color: "#1a1a1a", lineHeight: "1.1", letterSpacing: "-2px", maxWidth: "500px" }}>
          Know your risk before you take the pill.
        </div>
        <div style={{ fontSize: "14px", color: "#555", marginTop: "14px", letterSpacing: "1px", textTransform: "uppercase" }}>Drug-Gene Interaction Analysis · Powered by CPIC</div>
      </div>
    </div>
  );
}
