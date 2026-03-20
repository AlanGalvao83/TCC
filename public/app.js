const input = document.getElementById("videoInput")
const form = document.getElementById("uploadForm")
const preview = document.getElementById("previewVideo")
const resultBox = document.getElementById("result")
const overlayDownload = document.getElementById("overlayDownload")
const overlayGif = document.getElementById("overlayGif")
const bestFrame = document.getElementById("bestFrame")
input.addEventListener("change", e => { const f = input.files[0]; if (f) { preview.src = URL.createObjectURL(f) } })
form.addEventListener("submit", async e => { e.preventDefault(); const f = input.files[0]; if (!f) { return } resultBox.textContent = "Processando…"; const fd = new FormData(); fd.append("file", f, f.name); try { const r = await fetch("/analyze", { method: "POST", body: fd }); if (!r.ok) { resultBox.textContent = "Falha na análise"; return } const data = await r.json(); renderResult(data) } catch (err) { resultBox.textContent = "Erro ao conectar ao servidor" } })
async function renderResult(data) {
  const s = data.summary && data.summary.postura_ok;
  const angles = data.angles || {};
  const left = angles.left || {};
  const right = angles.right || {};
  const issuesL = (data.sides && data.sides.left && data.sides.left.issues) || [];
  const issuesR = (data.sides && data.sides.right && data.sides.right.issues) || [];
  const corrL = (data.sides && data.sides.left && data.sides.left.corrections) || {};
  const corrR = (data.sides && data.sides.right && data.sides.right.corrections) || {};
  const header = s ? `Postura geral: OK` : `Postura geral: Atenção`;
  const aL = `Lado esquerdo: tronco ${fmt(left.trunk)}°, joelho ${fmt(left.knee)}°, quadril ${fmt(left.hip)}°, tornozelo ${fmt(left.ankle)}°`;
  const aR = `Lado direito: tronco ${fmt(right.trunk)}°, joelho ${fmt(right.knee)}°, quadril ${fmt(right.hip)}°, tornozelo ${fmt(right.ankle)}°`;
  const il = issuesL.length ? annotateIssues(issuesL, corrL).map(i => `- ${i}`).join("\n") : "- Sem problemas relevantes";
  const ir = issuesR.length ? annotateIssues(issuesR, corrR).map(i => `- ${i}`).join("\n") : "- Sem problemas relevantes";
  const cl = listCorrections(corrL, "Esquerdo");
  const cr = listCorrections(corrR, "Direito");
  resultBox.textContent = [header, aL, aR, "Problemas esquerdo:", il, "Problemas direito:", ir, "Correções sugeridas:", cl, cr].join("\n\n");
  overlayGif.src = "";
  bestFrame.src = "";
  if (data.overlay_url) { overlayDownload.href = data.overlay_url }
  if (data.overlay_gif_url) {
    overlayGif.src = data.overlay_gif_url + "?ts=" + Date.now();
  }
  if (data.best_frame_url) {
    bestFrame.src = data.best_frame_url + "?ts=" + Date.now();
  }
}
function fmt(v) { if (v === undefined || v === null || Number.isNaN(v)) return "ND"; return Number.parseFloat(v).toFixed(1) }
function listCorrections(c, side) { const keys = Object.keys(c); if (!keys.length) return `${side}: nenhuma`; return `${side}: ` + keys.map(k => { const x = c[k]; return `${k}: valor ${fmt(x.valor)}°, ${x.direção}${x.corrigir ? ` ${fmt(x.corrigir)}°` : ``}` }).join("; ") }
function annotateIssues(issues, corrections) { return issues.map(s => { const k = keyFromIssue(s); const c = k && corrections[k]; if (c && c.corrigir && c.corrigir > 0) { return `${s} — corrigir ${fmt(c.corrigir)}° (${c.direção})` } return s }) }
function keyFromIssue(s) { const t = s.toLowerCase(); if (t.includes("tronco")) return "trunk"; if (t.includes("joelho")) return "knee"; if (t.includes("quadril")) return "hip"; if (t.includes("tornozelo")) return "ankle"; return null }
