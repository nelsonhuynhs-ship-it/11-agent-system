const API = "http://localhost:8100"

const AGENTS = [
  { name: "NÃO",  color: "#7c6cf8", role: "Lead" },
  { name: "ÉM",   color: "#f4a261", role: "Builder" },
  { name: "LÍNH", color: "#e63946", role: "Guard" },
  { name: "SOI",  color: "#2a9d8f", role: "Reviewer" },
  { name: "Ổ",    color: "#888",    role: "Memory" },
  { name: "NÓI",  color: "#7b2fbe", role: "Notifier" }
]

const tg = window.Telegram?.WebApp
if (tg) { tg.ready(); tg.expand() }

function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'))
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'))
  document.querySelector(`[onclick="showTab('${name}')"]`).classList.add('active')
  document.getElementById('tab-' + name).classList.add('active')
}

function renderAgents() {
  document.getElementById('agents-row').innerHTML = AGENTS.map(a => `
    <div class="agent-chip" style="border-color:${a.color};color:${a.color}">
      <span style="width:6px;height:6px;border-radius:50%;background:${a.color};display:inline-block"></span>
      ${a.name}
    </div>
  `).join('')
}

function timeAgo(ts) {
  if (!ts) return ''
  const diff = (Date.now() - new Date(ts)) / 60000
  if (diff < 1) return 'vừa xong'
  if (diff < 60) return Math.floor(diff) + 'm'
  return Math.floor(diff/60) + 'h'
}

function taskCard(t) {
  const isRunning = t.status === 'in_progress'
  return `
    <div class="task-card ${isRunning ? 'running' : ''}">
      <div class="task-title">${t.title || 'Task'}</div>
      <div class="task-owner">
        ${t.owner ? t.owner : '⏳'} · ${timeAgo(t.created_at)}
      </div>
      ${isRunning ? '<div class="progress-bar"><div class="progress-fill"></div></div>' : ''}
    </div>
  `
}

async function refresh() {
  try {
    const [tasks, log, health] = await Promise.all([
      fetch(API + '/agent/tasks').then(r => r.json()),
      fetch(API + '/agent/log').then(r => r.json()),
      fetch(API + '/agent/health').then(r => r.json())
    ])

    // Kanban
    const cols = { pending: [], in_progress: [], complete: [], failed: [] }
    ;(tasks.tasks || []).forEach(t => {
      if (cols[t.status]) cols[t.status].push(t)
    })

    document.getElementById('kanban').innerHTML = `
      <div class="kanban-col">
        <div class="col-header" style="color:#f4a261">⏳ Pending (${cols.pending.length})</div>
        ${cols.pending.slice(0,3).map(taskCard).join('')}
      </div>
      <div class="kanban-col">
        <div class="col-header" style="color:#7c6cf8">⚙️ Running (${cols.in_progress.length})</div>
        ${cols.in_progress.map(taskCard).join('')}
      </div>
      <div class="kanban-col">
        <div class="col-header" style="color:#2ecc71">✅ Done (${cols.complete.length})</div>
        ${cols.complete.slice(0,3).map(taskCard).join('')}
      </div>
      <div class="kanban-col">
        <div class="col-header" style="color:#e63946">❌ Failed (${cols.failed.length})</div>
        ${cols.failed.slice(0,3).map(taskCard).join('')}
      </div>
    `

    // Log
    document.getElementById('log-feed').innerHTML =
      (log.lines || []).slice(-20).reverse().map(l => {
        const cls = l.includes('✅') || l.includes('PASS') ? 'success'
                  : l.includes('❌') || l.includes('FAIL') ? 'error'
                  : l.includes('NÃO') || l.includes('ÉM') ? 'info' : ''
        return `<div class="log-line ${cls}">${l}</div>`
      }).join('')

    // Health
    document.getElementById('health-info').innerHTML = `
      <div class="health-item">
        <span>ERP Master</span>
        <span class="${health.erp_exists ? 'health-ok' : 'health-fail'}">
          ${health.erp_exists ? '✅ ' + health.erp_size_mb + ' MB' : '❌ Missing'}
        </span>
      </div>
      <div class="health-item">
        <span>Task DB</span>
        <span class="${health.task_db ? 'health-ok' : 'health-fail'}">
          ${health.task_db ? '✅ Online' : '❌ Missing'}
        </span>
      </div>
      <div class="health-item">
        <span>Mailbox DB</span>
        <span class="${health.mailbox_db ? 'health-ok' : 'health-fail'}">
          ${health.mailbox_db ? '✅ Online' : '❌ Missing'}
        </span>
      </div>
      <div class="health-item">
        <span>Agents</span>
        <span class="health-ok">${health.agents_count || 17} modules</span>
      </div>
    `
  } catch(e) {
    console.error('API error:', e)
  }
}

async function sendTask() {
  const text = document.getElementById('task-input').value.trim()
  if (!text) return

  document.getElementById('send-btn').textContent = '...'

  try {
    await fetch(API + '/agent/task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: text, description: text })
    })
    document.getElementById('task-input').value = ''
    if (tg) tg.showAlert('NÃO đã nhận task!')
    else alert('Task đã gửi!')
  } catch(e) {
    if (tg) tg.showAlert('Lỗi kết nối API')
  }

  document.getElementById('send-btn').textContent = 'Gửi'
  refresh()
}

renderAgents()
refresh()
setInterval(refresh, 3000)
