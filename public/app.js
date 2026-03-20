/* PosturaRun — app.js */
const videoInput    = document.getElementById('videoInput')
const uploadForm    = document.getElementById('uploadForm')
const previewVideo  = document.getElementById('previewVideo')
const previewWrap   = document.getElementById('previewWrap')
const btnAnalyze    = document.getElementById('btnAnalyze')
const loadingWrap   = document.getElementById('loadingWrap')
const resultSection = document.getElementById('resultSection')
const dropZone      = document.getElementById('dropZone')
const fileNameEl    = document.getElementById('fileName')
const overlayDownload = document.getElementById('overlayDownload')
const overlayGif    = document.getElementById('overlayGif')
const bestFrame     = document.getElementById('bestFrame')

// Targets biomecânicos para colorização
const TARGETS = {
  trunk:  { min: 4,   max: 8,   label: 'Tronco'    },
  knee:   { min: 150, max: 170, label: 'Joelho'    },
  hip:    { min: 165, max: 175, label: 'Quadril'   },
  ankle:  { min: 80,  max: 100, label: 'Tornozelo' },
}

// ---- Drag & Drop ----
;['dragenter','dragover'].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add('drag-over') }))
;['dragleave','drop'].forEach(ev => dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove('drag-over') }))
dropZone.addEventListener('drop', e => {
  const file = e.dataTransfer.files[0]
  if (file && file.type.startsWith('video/')) setFile(file)
})

// ---- File Select ----
videoInput.addEventListener('change', () => {
  if (videoInput.files[0]) setFile(videoInput.files[0])
})

function setFile(file) {
  fileNameEl.textContent = `📁 ${file.name} — ${(file.size / 1024 / 1024).toFixed(1)} MB`
  previewVideo.src = URL.createObjectURL(file)
  previewWrap.style.display = 'block'
  resultSection.style.display = 'none'
  loadingWrap.style.display = 'none'
}

// ---- Submit ----
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
    if (!res.ok) { showError('Falha na análise. Tente outro vídeo.'); return }
    const data = await res.json()
    if (data.error) { showError(data.error); return }
    renderResult(data)
  } catch {
    showError('Erro ao conectar ao servidor.')
  } finally {
    btnAnalyze.disabled = false
    loadingWrap.style.display = 'none'
  }
})

function showError(msg) {
  loadingWrap.style.display = 'none'
  resultSection.style.display = 'flex'
  document.getElementById('statusBanner').className = 'status-banner bad'
  document.getElementById('statusIcon').textContent = '❌'
  document.getElementById('statusTitle').textContent = 'Erro na análise'
  document.getElementById('statusSub').textContent = msg
  document.getElementById('anglesGrid').innerHTML = ''
  document.getElementById('issuesLeft').innerHTML = ''
  document.getElementById('issuesRight').innerHTML = ''
  document.getElementById('corrLeft').innerHTML = ''
  document.getElementById('corrRight').innerHTML = ''
  document.getElementById('visualsGrid').style.display = 'none'
  document.getElementById('downloadCard').style.display = 'none'
}

function fmt(v) {
  if (v === undefined || v === null || isNaN(v)) return '—'
  return Number(v).toFixed(1)
}

function angleClass(key, val) {
  if (isNaN(val)) return ''
  const t = TARGETS[key]
  if (!t) return ''
  if (val >= t.min && val <= t.max) return 'ok'
  const margin = (t.max - t.min) * 0.5
  if (val >= t.min - margin && val <= t.max + margin) return 'warn'
  return 'bad'
}

function renderResult(data) {
  const ok = data.summary && data.summary.postura_ok
  const angles = data.angles || {}
  const L = angles.left  || {}
  const R = angles.right || {}
  const sidesL = (data.sides && data.sides.left)  || {}
  const sidesR = (data.sides && data.sides.right) || {}

  // Status
  const banner = document.getElementById('statusBanner')
  banner.className = 'status-banner ' + (ok ? 'ok' : 'bad')
  document.getElementById('statusIcon').textContent  = ok ? '✅' : '⚠️'
  document.getElementById('statusTitle').textContent = ok ? 'Postura Adequada' : 'Ajustes Recomendados'
  document.getElementById('statusSub').textContent   = ok
    ? 'Seus ângulos biomecânicos estão dentro dos limites ideais.'
    : 'Foram identificados pontos de melhoria na sua postura de corrida.'

  // Angles Grid
  const grid = document.getElementById('anglesGrid')
  grid.innerHTML = Object.keys(TARGETS).map(key => {
    const lv = L[key]; const rv = R[key]
    const lc = angleClass(key, lv); const rc = angleClass(key, rv)
    return `
    <div class="angle-card">
      <div class="angle-label">${TARGETS[key].label}</div>
      <div class="angle-row">
        <div class="angle-side">
          <div class="angle-side-label">Esq</div>
          <div class="angle-val ${lc}">${fmt(lv)}<span class="angle-unit">°</span></div>
        </div>
        <div class="angle-side">
          <div class="angle-side-label">Dir</div>
          <div class="angle-val ${rc}">${fmt(rv)}<span class="angle-unit">°</span></div>
        </div>
      </div>
    </div>`
  }).join('')

  // Issues & Corrections — Esquerdo
  renderSide('issuesLeft', 'corrLeft', sidesL.issues || [], sidesL.corrections || {})
  // Issues & Corrections — Direito
  renderSide('issuesRight', 'corrRight', sidesR.issues || [], sidesR.corrections || {})

  // Visuals
  const visualsGrid = document.getElementById('visualsGrid')
  const gifCard  = document.getElementById('gifCard')
  const bestCard = document.getElementById('bestCard')
  let hasVisual = false

  if (data.overlay_gif_url) {
    overlayGif.src = data.overlay_gif_url + '?ts=' + Date.now()
    gifCard.style.display = 'block'
    hasVisual = true
  } else { gifCard.style.display = 'none' }

  if (data.best_frame_url) {
    bestFrame.src = data.best_frame_url + '?ts=' + Date.now()
    bestCard.style.display = 'block'
    hasVisual = true
  } else { bestCard.style.display = 'none' }

  visualsGrid.style.display = hasVisual ? 'grid' : 'none'

  // Download
  const downloadCard = document.getElementById('downloadCard')
  if (data.overlay_url) {
    overlayDownload.href = data.overlay_url
    downloadCard.style.display = 'block'
  } else {
    downloadCard.style.display = 'none'
  }

  resultSection.style.display = 'flex'
  resultSection.style.flexDirection = 'column'
  resultSection.style.gap = '16px'
  resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function renderSide(issuesId, corrId, issues, corrections) {
  const issuesEl = document.getElementById(issuesId)
  const corrEl   = document.getElementById(corrId)

  if (issues.length === 0) {
    issuesEl.innerHTML = `<ul class="issue-list"><li class="issue-item ok"><span class="issue-dot ok"></span>Sem problemas identificados</li></ul>`
  } else {
    issuesEl.innerHTML = `<ul class="issue-list">${issues.map(s => {
      const key = keyFromIssue(s)
      const c = key && corrections[key]
      const extra = c && c.corrigir > 0 ? ` — corrigir ${fmt(c.corrigir)}° (${c.direção})` : ''
      return `<li class="issue-item bad"><span class="issue-dot bad"></span>${s}${extra}</li>`
    }).join('')}</ul>`
  }

  const keys = Object.keys(corrections)
  if (keys.length === 0) { corrEl.innerHTML = ''; return }
  corrEl.innerHTML = `<div class="corr-title">Correções</div><div class="corr-list">${keys.map(k => {
    const x = corrections[k]
    const dir = x.direção || 'adequado'
    const tagClass = dir.toLowerCase().includes('aumentar') ? 'aumentar' : dir.toLowerCase().includes('reduzir') ? 'reduzir' : 'adequado'
    return `<div class="corr-item">
      <span class="corr-key">${TARGETS[k] ? TARGETS[k].label : k}:</span>
      ${fmt(x.valor)}°
      <span class="corr-tag ${tagClass}">${dir}${x.corrigir ? ' ' + fmt(x.corrigir) + '°' : ''}</span>
    </div>`
  }).join('')}</div>`
}

function keyFromIssue(s) {
  const t = s.toLowerCase()
  if (t.includes('tronco'))   return 'trunk'
  if (t.includes('joelho'))   return 'knee'
  if (t.includes('quadril'))  return 'hip'
  if (t.includes('tornozelo'))return 'ankle'
  return null
}
