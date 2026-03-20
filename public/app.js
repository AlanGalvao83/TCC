/* PosturaRun — app.js (com sidebar e KaTeX) */

// ================================================================
//  Navegação por seções
// ================================================================
const sections = {
  'analyzer':    'Analisador de Postura',
  'infographic': 'Infográfico',
  'mindmap':     'Mapa Mental',
  'podcast':     'Podcast',
  'tech':        'Análise Técnica',
}
const topbarTitle   = document.getElementById('topbarTitle')
const hamburger     = document.getElementById('hamburger')
const sidebar       = document.getElementById('sidebar')
const sidebarClose  = document.getElementById('sidebarClose')
const overlay       = document.getElementById('sidebarOverlay')

function openSidebar()  { sidebar.classList.add('open');  overlay.classList.add('open') }
function closeSidebar() { sidebar.classList.remove('open'); overlay.classList.remove('open') }
hamburger.addEventListener('click', openSidebar)
sidebarClose.addEventListener('click', closeSidebar)
overlay.addEventListener('click', closeSidebar)

function showSection(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'))
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'))
  const page = document.getElementById(id)
  if (page) page.classList.add('active')
  const navItem = document.querySelector(`[data-section="${id}"]`)
  if (navItem) navItem.classList.add('active')
  if (topbarTitle) topbarTitle.textContent = sections[id] || ''
  closeSidebar()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault()
    showSection(item.dataset.section)
  })
})

// ================================================================
//  KaTeX — Renderiza fórmulas na seção Análise Técnica
// ================================================================
function renderMath() {
  const opts = { displayMode: false, throwOnError: false }
  const disp = { displayMode: true,  throwOnError: false }

  const eqU = document.getElementById('eq-u')
  const eqV = document.getElementById('eq-v')
  const eqT = document.getElementById('eq-theta')
  const eqD = document.getElementById('eq-dot')
  const eqN = document.getElementById('eq-norm')

  if (typeof katex === 'undefined') return

  if (eqU) katex.render(String.raw`\vec{u} = A - B = (A_x - B_x,\; A_y - B_y)`, eqU, opts)
  if (eqV) katex.render(String.raw`\vec{v} = C - B = (C_x - B_x,\; C_y - B_y)`, eqV, opts)
  if (eqT) katex.render(String.raw`\theta = \arccos\!\left(\frac{\vec{u} \cdot \vec{v}}{|\vec{u}|\;|\vec{v}|}\right)`, eqT, disp)
  if (eqD) katex.render(String.raw`\vec{u} \cdot \vec{v} = u_x v_x + u_y v_y`, eqD, opts)
  if (eqN) katex.render(String.raw`|\vec{u}| = \sqrt{u_x^2 + u_y^2}`, eqN, opts)
}

// Aguarda KaTeX carregar (CDN)
if (typeof katex !== 'undefined') {
  renderMath()
} else {
  window.addEventListener('load', renderMath)
}

// ================================================================
//  Analisador de Postura
// ================================================================
const videoInput    = document.getElementById('videoInput')
const uploadForm    = document.getElementById('uploadForm')
const previewVideo  = document.getElementById('previewVideo')
const previewWrap   = document.getElementById('previewWrap')
const btnAnalyze    = document.getElementById('btnAnalyze')
const loadingWrap   = document.getElementById('loadingWrap')
const resultSection = document.getElementById('resultSection')
const dropZone      = document.getElementById('dropZone')
const fileNameEl    = document.getElementById('fileName')

const TARGETS = {
  trunk:  { min: 4,   max: 8,   label: 'Tronco' },
  knee:   { min: 150, max: 170, label: 'Joelho' },
  hip:    { min: 165, max: 175, label: 'Quadril' },
  ankle:  { min: 80,  max: 100, label: 'Tornozelo' },
}

// Drag & Drop
;['dragenter','dragover'].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add('drag-over') }))
;['dragleave','drop'].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove('drag-over') }))
dropZone.addEventListener('drop', e => {
  const file = e.dataTransfer.files[0]
  if (file && file.type.startsWith('video/')) setFile(file)
})
videoInput.addEventListener('change', () => { if (videoInput.files[0]) setFile(videoInput.files[0]) })

function setFile(file) {
  fileNameEl.textContent = `📁 ${file.name} — ${(file.size / 1024 / 1024).toFixed(1)} MB`
  previewVideo.src = URL.createObjectURL(file)
  previewWrap.style.display = 'block'
  resultSection.style.display = 'none'
  loadingWrap.style.display = 'none'
}

uploadForm.addEventListener('submit', async e => {
  e.preventDefault()
  const file = videoInput.files[0]
  if (!file) return
  btnAnalyze.disabled = true
  loadingWrap.style.display = 'block'
  resultSection.style.display = 'none'
  try {
    const fd = new FormData()
    fd.append('file', file, file.name)
    const res = await fetch('/analyze', { method: 'POST', body: fd })
    if (!res.ok) { showError('Falha na análise.'); return }
    const data = await res.json()
    if (data.error) { showError(data.error); return }
    renderResult(data)
  } catch { showError('Erro ao conectar ao servidor.') }
  finally { btnAnalyze.disabled = false; loadingWrap.style.display = 'none' }
})

function showError(msg) {
  loadingWrap.style.display = 'none'
  resultSection.style.display = 'flex'
  document.getElementById('statusBanner').className = 'status-banner bad'
  document.getElementById('statusIcon').textContent  = '❌'
  document.getElementById('statusTitle').textContent = 'Erro na análise'
  document.getElementById('statusSub').textContent   = msg
  document.getElementById('anglesGrid').innerHTML = ''
  document.getElementById('issuesLeft').innerHTML = ''
  document.getElementById('issuesRight').innerHTML = ''
  document.getElementById('corrLeft').innerHTML = ''
  document.getElementById('corrRight').innerHTML = ''
  document.getElementById('visualsGrid').style.display = 'none'
  document.getElementById('downloadCard').style.display = 'none'
}

function fmt(v) { return (v === undefined || v === null || isNaN(v)) ? '—' : Number(v).toFixed(1) }

function angleClass(key, val) {
  if (isNaN(val)) return ''
  const t = TARGETS[key]; if (!t) return ''
  if (val >= t.min && val <= t.max) return 'ok'
  const m = (t.max - t.min) * .5
  if (val >= t.min - m && val <= t.max + m) return 'warn'
  return 'bad'
}

function renderResult(data) {
  const ok = data.summary && data.summary.postura_ok
  const L = (data.angles && data.angles.left)  || {}
  const R = (data.angles && data.angles.right) || {}
  const sidesL = (data.sides && data.sides.left)  || {}
  const sidesR = (data.sides && data.sides.right) || {}

  document.getElementById('statusBanner').className = 'status-banner ' + (ok ? 'ok' : 'bad')
  document.getElementById('statusIcon').textContent  = ok ? '✅' : '⚠️'
  document.getElementById('statusTitle').textContent = ok ? 'Postura Adequada' : 'Ajustes Recomendados'
  document.getElementById('statusSub').textContent   = ok
    ? 'Seus ângulos biomecânicos estão dentro dos limites ideais.'
    : 'Foram identificados pontos de melhoria na sua postura de corrida.'

  document.getElementById('anglesGrid').innerHTML = Object.keys(TARGETS).map(key => {
    const lv = L[key], rv = R[key]
    return `<div class="angle-card">
      <div class="angle-label">${TARGETS[key].label}</div>
      <div class="angle-row">
        <div class="angle-side"><div class="angle-side-label">Esq</div><div class="angle-val ${angleClass(key,lv)}">${fmt(lv)}<span class="angle-unit">°</span></div></div>
        <div class="angle-side"><div class="angle-side-label">Dir</div><div class="angle-val ${angleClass(key,rv)}">${fmt(rv)}<span class="angle-unit">°</span></div></div>
      </div></div>`
  }).join('')

  renderSide('issuesLeft',  'corrLeft',  sidesL.issues || [], sidesL.corrections || {})
  renderSide('issuesRight', 'corrRight', sidesR.issues || [], sidesR.corrections || {})

  const gifCard  = document.getElementById('gifCard')
  const bestCard = document.getElementById('bestCard')
  const vg = document.getElementById('visualsGrid')
  let hasV = false
  if (data.overlay_gif_url) { document.getElementById('overlayGif').src = data.overlay_gif_url + '?ts=' + Date.now(); gifCard.style.display='block'; hasV=true } else gifCard.style.display='none'
  if (data.best_frame_url)  { document.getElementById('bestFrame').src  = data.best_frame_url  + '?ts=' + Date.now(); bestCard.style.display='block'; hasV=true } else bestCard.style.display='none'
  vg.style.display = hasV ? 'grid' : 'none'

  const dc = document.getElementById('downloadCard')
  if (data.overlay_url) { document.getElementById('overlayDownload').href = data.overlay_url; dc.style.display='block' } else dc.style.display='none'

  resultSection.style.display = 'flex'
  resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function renderSide(issId, corrId, issues, corrections) {
  const ie = document.getElementById(issId)
  const ce = document.getElementById(corrId)
  ie.innerHTML = issues.length === 0
    ? `<ul class="issue-list"><li class="issue-item ok"><span class="issue-dot ok"></span>Sem problemas identificados</li></ul>`
    : `<ul class="issue-list">${issues.map(s => {
        const k = keyFromIssue(s); const c = k && corrections[k]
        const extra = c && c.corrigir > 0 ? ` — corrigir ${fmt(c.corrigir)}° (${c.direção})` : ''
        return `<li class="issue-item bad"><span class="issue-dot bad"></span>${s}${extra}</li>`
      }).join('')}</ul>`

  const keys = Object.keys(corrections)
  ce.innerHTML = keys.length === 0 ? '' : `<div class="corr-title">Correções</div><div class="corr-list">${keys.map(k => {
    const x = corrections[k]; const dir = x.direção || 'adequado'
    const tc = dir.toLowerCase().includes('aumentar') ? 'aumentar' : dir.toLowerCase().includes('reduzir') ? 'reduzir' : 'adequado'
    return `<div class="corr-item"><span class="corr-key">${TARGETS[k]?TARGETS[k].label:k}:</span>${fmt(x.valor)}°<span class="corr-tag ${tc}">${dir}${x.corrigir?' '+fmt(x.corrigir)+'°':''}</span></div>`
  }).join('')}</div>`
}

function keyFromIssue(s) {
  const t = s.toLowerCase()
  if (t.includes('tronco'))    return 'trunk'
  if (t.includes('joelho'))    return 'knee'
  if (t.includes('quadril'))   return 'hip'
  if (t.includes('tornozelo')) return 'ankle'
  return null
}
