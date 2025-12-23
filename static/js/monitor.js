let charts = {};
let names = {};
let activeIP = null;

let groups = {};
let activeGroup = null;

// =========================
// LOAD HOSTS
// =========================
async function loadHosts() {
    const res = await fetch('/hosts/groups');
    const data = await res.json();

    groups = data.groups || {};
    renderGroupTabs();
}

document.addEventListener('DOMContentLoaded', loadHosts);

// =========================
// GRUPOS
// =========================
async function addGroup() {
    const input = document.getElementById('groupInput');
    const name = input.value.trim();
    if (!name || groups[name]) return;

    const res = await fetch('/groups/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    });

    const json = await res.json();
    if (json.status !== 'ok') return;

    groups[name] = { hosts: [] };
    input.value = '';
    renderGroupTabs();
}

function renderGroupTabs() {
    const container = document.getElementById('group-tabs');
    container.innerHTML = '';

    for (const groupName in groups) {
        const tab = document.createElement('div');
        tab.className = 'tab up';
        tab.innerText = groupName;
        tab.onclick = () => activateGroup(groupName);

        const closeBtn = document.createElement('span');
        closeBtn.className = 'close';
        closeBtn.innerText = 'x';
        closeBtn.onclick = e => {
            e.stopPropagation();
            confirmRemoveGroup(groupName);
        };

        tab.appendChild(closeBtn);
        container.appendChild(tab);
    }
}

function activateGroup(groupName) {
    activeGroup = groupName;

    charts = {};
    names = {};
    activeIP = null;

    document.getElementById('tabs').innerHTML = '';
    document.getElementById('panels').innerHTML = '';
    document.getElementById('ip-form').style.display = 'block';

    for (const h of groups[groupName].hosts || []) {
        addHostFromConfig(h.name, h.ip);
    }
}

function confirmRemoveGroup(groupName) {
    if (!confirm(`Excluir o grupo "${groupName}"?`)) return;
    removeGroup(groupName);
}

async function removeGroup(groupName) {
    await fetch('/groups/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: groupName })
    });

    delete groups[groupName];
    renderGroupTabs();
}

// =========================
// HOSTS
// =========================
async function addIP() {
    if (!activeGroup) return;

    const nameInput = document.getElementById('nameInput');
    const ipInput = document.getElementById('ipInput');

    const name = nameInput.value.trim();
    const ip = ipInput.value.trim();
    if (!ip || charts[ip]) return;

    nameInput.value = '';
    ipInput.value = '';

    await fetch('/add_ip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip, name: name || ip, group: activeGroup })
    });

    groups[activeGroup].hosts.push({ ip, name: name || ip });
    addHostFromConfig(name || ip, ip);
}

async function removeIP(ip) {
    document.getElementById(`tab-${ip}`)?.remove();
    document.getElementById(`panel-${ip}`)?.remove();

    delete charts[ip];
    delete names[ip];

    for (const g of Object.values(groups)) {
        g.hosts = g.hosts.filter(h => h.ip !== ip);
    }

    await fetch('/remove_ip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip })
    });
}

function addHostFromConfig(name, ip) {
    if (charts[ip]) return;

    names[ip] = name;

    const tab = document.createElement('div');
    tab.id = `tab-${ip}`;
    tab.className = 'tab up';
    tab.innerText = name;
    tab.onclick = () => activateTab(ip);

    const closeBtn = document.createElement('span');
    closeBtn.className = 'close';
    closeBtn.innerText = 'x';
    closeBtn.onclick = e => {
        e.stopPropagation();
        removeIP(ip);
    };

    tab.appendChild(closeBtn);
    document.getElementById('tabs').appendChild(tab);

    const panel = document.createElement('div');
    panel.id = `panel-${ip}`;
    panel.className = 'panel';

    const canvas = document.createElement('canvas');
    panel.appendChild(canvas);
    document.getElementById('panels').appendChild(panel);

    charts[ip] = new Chart(canvas, {
        type: 'line',
        data: { labels: [], datasets: [{ data: [] }] },
        options: { responsive: true }
    });

    activateTab(ip);
}

// =========================
// UI
// =========================
function activateTab(ip) {
    activeIP = ip;

    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`panel-${ip}`).classList.add('active');
}

async function updateCharts() {
    const res = await fetch('/data');
    const data = await res.json();

    for (const ip in data) {
        if (!charts[ip]) continue;

        const history = data[ip];
        const last = history.at(-1);

        charts[ip].data.labels = history.map(v =>
            new Date(v.ts * 1000).toLocaleTimeString()
        );
        charts[ip].data.datasets[0].data = history.map(v => v.latency ?? NaN);

        const tab = document.getElementById(`tab-${ip}`);
        tab.className = `tab ${last.status.toLowerCase()}`;

        charts[ip].update();
    }
}

setInterval(updateCharts, 2000);
