// Global State
let jobsData = [];
let selectedJobName = null;
let logEventSource = null;

// DOM Elements
const jobListEl = document.getElementById('job-list');
const detailJobNameEl = document.getElementById('detail-job-name');
const detailJobFileEl = document.getElementById('detail-job-file');
const detailJobDescEl = document.getElementById('detail-job-desc');
const dynamicParamsEl = document.getElementById('dynamic-params-container');
const executeBtn = document.getElementById('btn-execute');
const stopBtn = document.getElementById('btn-stop');
const saveConfigBtn = document.getElementById('btn-save-config');
const resetBtn = document.getElementById('btn-reset');
const clearLogBtn = document.getElementById('btn-clear-log');
const refreshBtn = document.getElementById('btn-refresh');
const consoleOutputEl = document.getElementById('console-output');
const consoleBodyEl = document.querySelector('.console-body');
const statusMessageEl = document.getElementById('status-message');
const statusBarEl = document.getElementById('statusbar');
const clockEl = document.getElementById('live-clock');
const badgeEl = document.getElementById('global-status-badge');

// Database Settings Elements
const dbServerEl = document.getElementById('db-server');
const dbUserEl = document.getElementById('db-user');
const dbPwdEl = document.getElementById('db-pwd');
const dbNameEl = document.getElementById('db-name');

// ── Clock Initialization ──────────────────────────────────────────────────────
function updateClock() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const day = pad(now.getDate());
    const month = pad(now.getMonth() + 1);
    const year = now.getFullYear();
    const hours = pad(now.getHours());
    const minutes = pad(now.getMinutes());
    const seconds = pad(now.getSeconds());
    
    clockEl.textContent = `🕐  ${day}/${month}/${year}   ${hours}:${minutes}:${seconds}`;
}
setInterval(updateClock, 1000);
updateClock();

// ── API Functions ─────────────────────────────────────────────────────────────
async function loadJobs(autoSelect = true) {
    try {
        const response = await fetch('/api/jobs');
        if (!response.ok) throw new Error('Gagal mengambil data jobs');
        jobsData = await response.json();
        
        renderJobList();
        
        if (autoSelect && jobsData.length > 0) {
            if (selectedJobName) {
                const stillExists = jobsData.find(j => j.name === selectedJobName);
                if (stillExists) {
                    selectJob(selectedJobName, false);
                    return;
                }
            }
            selectJob(jobsData[0].name, false);
        }
    } catch (err) {
        console.error(err);
        showStatus('Gagal memuat daftar pekerjaan', 'error');
    }
}

async function loadDbConfig() {
    try {
        const response = await fetch('/api/db-config');
        if (!response.ok) throw new Error('Gagal mengambil db config');
        const dbConfig = await response.json();
        
        dbServerEl.value = dbConfig.server || '';
        dbUserEl.value = dbConfig.user || '';
        dbPwdEl.value = dbConfig.pwd || '';
        dbNameEl.value = dbConfig.name || '';
    } catch (err) {
        console.error(err);
    }
}

async function saveDbConfig() {
    const payload = {
        server: dbServerEl.value.trim(),
        user: dbUserEl.value.trim(),
        pwd: dbPwdEl.value.trim(),
        name: dbNameEl.value.trim()
    };
    
    try {
        const response = await fetch('/api/db-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        showStatus('Database settings disimpan', 'success');
        logToConsole('OK', 'Database Settings tersimpan.');
        return true;
    } catch (err) {
        console.error(err);
        showStatus('Gagal menyimpan database settings', 'error');
        logToConsole('ERROR', `Gagal menyimpan Database Settings: ${err && err.message ? err.message : err}`);
        return false;
    }
}

// ── Rendering Functions ───────────────────────────────────────────────────────
function renderJobList() {
    jobListEl.innerHTML = '';
    
    jobsData.forEach(job => {
        const li = document.createElement('li');
        if (job.name === selectedJobName) {
            li.classList.add('active');
        }
        
        let statusBadgeClass = 'idle';
        let statusText = 'Idle';
        
        if (job.status === 'running') {
            statusBadgeClass = 'running';
            statusText = 'Running';
        } else if (job.status === 'success') {
            statusBadgeClass = 'success';
            statusText = 'Success';
        } else if (job.status === 'failed') {
            statusBadgeClass = 'failed';
            statusText = 'Failed';
        }
        
        const shortName = job.name.split('–')[0].trim();
        
        li.innerHTML = `
            <div class="job-item-header">
                <span class="job-item-name">${shortName}</span>
                <span class="badge ${statusBadgeClass}">⬤ ${statusText}</span>
            </div>
            <span class="job-item-file">${job.file}</span>
        `;
        
        li.addEventListener('click', () => selectJob(job.name));
        jobListEl.appendChild(li);
    });
}

function selectJob(jobName, reloadUI = true) {
    selectedJobName = jobName;
    const job = jobsData.find(j => j.name === jobName);
    if (!job) return;
    
    // Highlight di list
    const items = jobListEl.querySelectorAll('li');
    jobsData.forEach((j, index) => {
        if (j.name === jobName) {
            items[index]?.classList.add('active');
        } else {
            items[index]?.classList.remove('active');
        }
    });
    
    // Update Meta Info
    detailJobNameEl.textContent = job.name;
    detailJobFileEl.textContent = job.file;
    detailJobDescEl.textContent = job.desc;
    
    // Update Badge Status
    badgeEl.className = `badge ${job.status}`;
    badgeEl.textContent = `⬤ ${job.status.charAt(0).toUpperCase() + job.status.slice(1)}`;
    
    // Mengatur Tombol Execute
    if (job.status === 'running') {
        executeBtn.disabled = true;
        executeBtn.textContent = '⬤ Running...';
        if (stopBtn) stopBtn.disabled = false;
        // Auto sambungkan ke stream log jika sedang jalan
        connectLogStream(job.name);
    } else {
        executeBtn.disabled = false;
        executeBtn.textContent = '▶ Execute Job';
        if (stopBtn) stopBtn.disabled = true;
        // Jika sebelumnya ada stream log aktif untuk job lain, putuskan
        disconnectLogStream();
    }
    
    if (reloadUI) {
        renderParamsForm(job.params);
    }
}

function renderParamsForm(params) {
    dynamicParamsEl.innerHTML = '';
    
    params.forEach(p => {
        const row = document.createElement('div');
        row.className = 'form-group-row';
        
        const label = document.createElement('label');
        label.textContent = p.label + ':';
        row.appendChild(label);
        
        const inputContainer = document.createElement('div');
        inputContainer.className = 'input-container';
        
        let inputEl;
        
        if (p.type === 'bool') {
            inputEl = document.createElement('select');
            inputEl.innerHTML = `
                <option value="True" ${String(p.value).toLowerCase() === 'true' ? 'selected' : ''}>True</option>
                <option value="False" ${String(p.value).toLowerCase() === 'false' ? 'selected' : ''}>False</option>
            `;
            inputEl.style.width = '120px';
        } else if (p.type === 'date') {
            inputEl = document.createElement('input');
            inputEl.type = 'date';
            inputEl.value = p.value;
            inputEl.style.width = '200px';
        } else if (p.type === 'path') {
            const wrapper = document.createElement('div');
            wrapper.className = 'path-input-wrapper';
            
            inputEl = document.createElement('input');
            inputEl.type = 'text';
            inputEl.value = p.value;
            
            const browseBtn = document.createElement('button');
            browseBtn.type = 'button';
            browseBtn.className = 'toolbar-btn';
            browseBtn.textContent = '…';
            browseBtn.style.padding = '8px 14px';
            
            // Tambahkan dialog browser via backend
            browseBtn.addEventListener('click', async () => {
                const browseType = p.arg.toLowerCase().includes('folder') || p.arg.toLowerCase().includes('save') ? 'folder' : 'file';
                try {
                    const res = await fetch('/api/utils/browse', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ type: browseType, current_value: inputEl.value })
                    });
                    if (res.ok) {
                        const data = await res.json();
                        if (data.path) {
                            inputEl.value = data.path;
                        }
                    }
                } catch (err) {
                    console.error('Browser error:', err);
                }
            });
            
            wrapper.appendChild(inputEl);
            wrapper.appendChild(browseBtn);
            inputContainer.appendChild(wrapper);
        } else {
            inputEl = document.createElement('input');
            inputEl.type = 'text';
            inputEl.value = p.value;
            inputEl.style.width = p.type === 'int' ? '120px' : '280px';
        }
        
        if (p.type !== 'path') {
            inputContainer.appendChild(inputEl);
        }
        
        inputEl.id = `param-${p.arg}`;
        inputEl.dataset.arg = p.arg;
        
        // Help text
        const helpText = document.createElement('span');
        helpText.className = 'help-text';
        helpText.textContent = p.help;
        inputContainer.appendChild(helpText);
        
        row.appendChild(inputContainer);
        dynamicParamsEl.appendChild(row);
    });
}

// ── Control Operations ────────────────────────────────────────────────────────
function getFormParameters() {
    const job = jobsData.find(j => j.name === selectedJobName);
    if (!job) return {};
    
    const params = {};
    job.params.forEach(p => {
        const input = document.getElementById(`param-${p.arg}`);
        if (input) {
            params[p.arg] = input.value;
        }
    });
    return params;
}

async function saveConfig() {
    if (!selectedJobName) {
        logToConsole('WARN', 'Tidak ada job yang dipilih.');
        return;
    }

    const params = getFormParameters();

    // 1) Simpan konfigurasi JOB (folder, periode, dll) — bagian terpenting.
    //    Dijalankan DULUAN & independen agar tidak bisa dibatalkan oleh
    //    masalah pada Database Settings.
    try {
        logToConsole('SYSTEM', `Menyimpan konfigurasi job: ${selectedJobName} ...`);
        const response = await fetch('/api/jobs/save-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job_name: selectedJobName,
                params: params
            })
        });

        if (!response.ok) throw new Error('HTTP ' + response.status);
        showStatus('Konfigurasi berhasil disimpan!', 'success');

        // Feedback eksplisit di panel log: tampilkan nilai yang tersimpan
        logToConsole('OK', `Konfigurasi tersimpan untuk job: ${selectedJobName}`);
        Object.entries(params).forEach(([arg, val]) => {
            const shown = String(val).trim() !== '' ? val : '(kosong)';
            logToConsole('INFO', `    • ${arg} = ${shown}`);
        });

        // Reload job structure to reflect in UI memory
        await loadJobs(false);
    } catch (err) {
        console.error(err);
        showStatus('Gagal menyimpan konfigurasi', 'error');
        logToConsole('ERROR', `Gagal menyimpan konfigurasi job: ${err && err.message ? err.message : err}. Pastikan server berjalan.`);
    }

    // 2) Simpan Database Settings secara terpisah. Apa pun hasilnya, TIDAK
    //    memengaruhi penyimpanan konfigurasi job di atas.
    try {
        await saveDbConfig();
    } catch (err) {
        console.error(err);
        logToConsole('WARN', `Database Settings tidak tersimpan: ${err && err.message ? err.message : err}`);
    }
}

function resetDefault() {
    const job = jobsData.find(j => j.name === selectedJobName);
    if (!job) return;
    
    // Reset inputs to original backend default
    job.params.forEach(p => {
        const input = document.getElementById(`param-${p.arg}`);
        if (input) {
            if (p.type === 'bool') {
                input.value = p.value; // Keeps current saved, but if we want default, we need job details from original schema
            }
            // For true default reset, reload jobs from API
        }
    });
    loadJobs(true); // Easiest way is to reload everything
    showStatus('Parameter dikembalikan ke nilai default', 'info');
    logToConsole('SYSTEM', `Parameter job '${selectedJobName}' dikembalikan ke nilai default.`);
}

async function executeJob() {
    if (!selectedJobName) return;
    
    // Save config first
    await saveConfig();
    
    const params = getFormParameters();
    
    executeBtn.disabled = true;
    executeBtn.textContent = '⬤ Running...';
    if (stopBtn) stopBtn.disabled = false;
    
    // Clear terminal log screen for fresh look
    consoleOutputEl.innerHTML = '';
    
    try {
        const response = await fetch('/api/jobs/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job_name: selectedJobName,
                params: params
            })
        });
        
        const result = await response.json();
        
        if (result.status === 'already running') {
            showStatus('Job ini sedang berjalan.', 'info');
        } else {
            showStatus('Job berhasil dijalankan!', 'success');
        }
        
        // Hubungkan ke stream log
        connectLogStream(selectedJobName);
        
        // Refresh sidebar
        await loadJobs(false);
    } catch (err) {
        console.error(err);
        showStatus('Gagal mengeksekusi job', 'error');
        executeBtn.disabled = false;
        executeBtn.textContent = '▶ Execute Job';
        if (stopBtn) stopBtn.disabled = true;
    }
}

// ── Stop Job ──────────────────────────────────────────────────────────────────
async function stopJob() {
    if (!selectedJobName) return;
    if (!confirm(`Hentikan job "${selectedJobName}"?`)) return;

    try {
        const response = await fetch('/api/jobs/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_name: selectedJobName })
        });
        const result = await response.json();
        showStatus(result.message || 'Permintaan stop dikirim', 'info');
    } catch (err) {
        console.error(err);
        showStatus('Gagal menghentikan job', 'error');
    }
}

// ── Log Stream (SSE) ──────────────────────────────────────────────────────────
function connectLogStream(jobName) {
    disconnectLogStream();
    
    // Bersihkan layar log
    consoleOutputEl.innerHTML = '';
    
    const url = `/api/jobs/stream-log?job_name=${encodeURIComponent(jobName)}`;
    logEventSource = new EventSource(url);
    
    logEventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.text) {
            appendLogLine(data.tag, data.text);
        }
        
        // Cek apakah ada marker selesai
        if (data.done || data.text.includes('[SYSTEM] Eksekusi job selesai.') || data.text.includes('[SYSTEM] Proses selesai.')) {
            disconnectLogStream();
            loadJobs(false); // Refresh status di sidebar
            
            // Kembalikan status execute button
            executeBtn.disabled = false;
            executeBtn.textContent = '▶ Execute Job';
            if (stopBtn) stopBtn.disabled = true;
        }
    };
    
    logEventSource.onerror = (err) => {
        console.error('SSE Error:', err);
        disconnectLogStream();
    };
}

function disconnectLogStream() {
    if (logEventSource) {
        logEventSource.close();
        logEventSource = null;
    }
}

function appendLogLine(tag, text) {
    const span = document.createElement('span');
    span.className = `log-${tag}`;
    span.textContent = text + '\n';
    
    consoleOutputEl.appendChild(span);
    
    // Auto Scroll ke bawah
    consoleBodyEl.scrollTop = consoleBodyEl.scrollHeight;
}

// Tulis baris log dengan stempel waktu (untuk aksi sisi-klien spt Save/Reset)
function logToConsole(tag, message) {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const ts = `[${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}]`;
    appendLogLine(tag, `${ts} [${tag}]  ${message}`);
}

// ── Login SAP (jalankan LoginSAP.vbs dari .env) ───────────────────────────────
async function loginSap() {
    logToConsole('SYSTEM', 'Menjalankan login SAP (LoginSAP.vbs) dari kredensial .env...');
    try {
        const res = await fetch('/api/sap/login', { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || ('HTTP ' + res.status));
        logToConsole('INFO', data.message || 'LoginSAP.vbs dijalankan.');
        showStatus('Login SAP dijalankan...', 'info');
        // Auto cek status setelah beberapa detik
        logToConsole('SYSTEM', 'Mengecek status otomatis dalam 12 detik...');
        setTimeout(testSapStatus, 12000);
    } catch (err) {
        console.error(err);
        logToConsole('ERROR', `Gagal menjalankan Login SAP: ${err && err.message ? err.message : err}`);
        showStatus('Gagal menjalankan Login SAP', 'error');
    }
}

// ── Test Status SAP GUI Scripting ─────────────────────────────────────────────
async function testSapStatus() {
    logToConsole('SYSTEM', 'Mengecek status SAP GUI Scripting...');
    try {
        const res = await fetch('/api/sap/status');
        const s = await res.json();
        logToConsole('INFO', `SAP GUI tersedia : ${s.available}`);
        logToConsole('INFO', `Jumlah koneksi   : ${s.connections}`);
        logToConsole('INFO', `Jumlah session   : ${s.sessions}`);
        logToConsole('INFO', `DisabledByServer : ${s.disabled_by_server}`);
        logToConsole('INFO', `Sudah login      : ${s.logged_in}`);
        (s.messages || []).forEach(m => {
            const tag = (m.toUpperCase().includes('DIBLOKIR') || m.toLowerCase().includes('tidak') || m.toLowerCase().includes('belum')) ? 'WARN' : 'INFO';
            logToConsole(tag, m);
        });

        if (s.disabled_by_server === true) {
            logToConsole('ERROR', 'Scripting DIBLOKIR server. Hubungi Basis untuk set sapgui/user_scripting = TRUE.');
            showStatus('SAP scripting diblokir server', 'error');
        } else if (s.logged_in) {
            logToConsole('OK', 'SAP siap untuk otomatisasi (scripting aktif & sudah login).');
            showStatus('SAP scripting OK & login', 'success');
        } else if (!s.available) {
            showStatus('SAP GUI tidak berjalan', 'error');
        } else {
            showStatus('Cek status SAP selesai', 'info');
        }
    } catch (err) {
        console.error(err);
        logToConsole('ERROR', 'Gagal menghubungi server untuk cek status SAP. Pastikan server berjalan.');
        showStatus('Gagal cek status SAP', 'error');
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function showStatus(msg, type = 'info') {
    statusMessageEl.textContent = msg;

    if (!statusBarEl) return;
    if (type === 'error') {
        statusBarEl.style.backgroundColor = 'var(--error)';
    } else if (type === 'success') {
        statusBarEl.style.backgroundColor = 'var(--success)';
    } else {
        statusBarEl.style.backgroundColor = 'var(--sap-blue)';
    }
    
    // Kembalikan ke warna standard setelah 4 detik
    setTimeout(() => {
        statusMessageEl.textContent = 'Ready';
        statusBarEl.style.backgroundColor = 'var(--sap-blue)';
    }, 4000);
}

// ── Event Listeners ──────────────────────────────────────────────────────────
executeBtn.addEventListener('click', executeJob);
if (stopBtn) stopBtn.addEventListener('click', stopJob);
saveConfigBtn.addEventListener('click', saveConfig);
resetBtn.addEventListener('click', resetDefault);
clearLogBtn.addEventListener('click', () => {
    consoleOutputEl.innerHTML = '';
    appendLogLine('SYSTEM', 'Log dibersihkan.');
});
refreshBtn.addEventListener('click', () => {
    loadJobs(false);
    loadDbConfig();
    showStatus('Data di-refresh', 'success');
});
const testSapBtn = document.getElementById('btn-test-sap');
if (testSapBtn) testSapBtn.addEventListener('click', testSapStatus);
const loginSapBtn = document.getElementById('btn-login-sap');
if (loginSapBtn) loginSapBtn.addEventListener('click', loginSap);

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    logToConsole('SYSTEM', 'app.js v3.1 termuat (no-cache aktif). Siap.');
    loadJobs(true);
    loadDbConfig();
});
