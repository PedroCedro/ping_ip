let charts = {};
let names = {};
let activeIP = null;
let draggedTab = null;

let groups = {};
let activeGroup = null;

const MAX_HOSTS = 60;

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

    groups[name] = {
        order: Object.keys(groups).length + 1,
        hosts: []
    };

    input.value = '';
    renderGroupTabs();
}

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
// RENDER GROUP TABS
// =========================
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
        closeBtn.onclick = (e) => {
            e.stopPropagation();
            confirmRemoveGroup(groupName);
        };

        tab.appendChild(closeBtn);
        container.appendChild(tab);
    }
}

// =========================
// ATIVAR GRUPO
// =========================
function activateGroup(groupName) {
    activeGroup = groupName;

    charts = {};
    names = {};
    activeIP = null;

    document.getElementById('tabs').innerHTML = '';
    document.getElementById('panels').innerHTML = '';
    document.getElementById('ip-form').style.display = 'block';

    const hosts = groups[groupName]?.hosts || [];
    for (const h of hosts) {
        addHostFromConfig(h.name, h.ip);
    }
}

// =========================
// CONFIRM / REMOVE GROUP
// =========================
function confirmRemoveGroup(groupName) {
    const ok = confirm(
        `Você está prestes a excluir a aba "${groupName}" e suas sub-abas.\n\nDeseja continuar?`
    );
    if (!ok) return;
    removeGroup(groupName);
}

async function removeGroup(groupName) {
    await fetch('/groups/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: groupName })
    });

    delete groups[groupName];

    if (activeGroup === groupName) {
        activeGroup = null;
        document.getElementById('tabs').innerHTML = '';
        document.getElementById('panels').innerHTML = '';
        document.getElementById('ip-form').style.display = 'none';
    }

    renderGroupTabs();
}

// =========================
// ADD HOST FROM CONFIG
// =========================
async function addHostFromConfig(name, ip) {
    if (!ip || charts[ip]) return;

    names[ip] = name || ip;

    const tab = document.createElement('div');
    tab.id = `tab-${ip}`;
    tab.className = 'tab up';
    tab.innerText = names[ip];
    tab.title = ip;
    tab.onclick = () => activateTab(ip);

    const closeBtn = document.createElement('span');
    closeBtn.className = 'close';
    closeBtn.innerText = 'x';
    closeBtn.onclick = (e) => {
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
        data: {
            labels: [],
            datasets: [{
                label: `Ping ${names[ip]}`,
                data: [],
                borderWidth: 2,
                tension: 0.2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });

    if (!activeIP) activateTab(ip);
}

// =========================
// ADD IP (BUG FIX AQUI)
// =========================
async function addIP() {
    console.log('Grupo ativo:', activeGroup);

    const nameInput = document.getElementById('nameInput');
    const ipInput = document.getElementById('ipInput');

    const name = nameInput.value.trim();
    const ip = ipInput.value.trim();

    if (!ip || charts[ip] || !activeGroup) return;

    names[ip] = name || ip;

    nameInput.value = '';
    ipInput.value = '';

    await fetch('/add_ip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            ip,
            name: names[ip],
            group: activeGroup
        })
    });

    // 🔥 CORREÇÃO CRÍTICA
    groups[activeGroup].hosts.push({
        ip,
        name: names[ip]
    });

    addHostFromConfig(names[ip], ip);
}

// =========================
// REMOVE IP
// =========================
async function removeIP(ip) {
    document.getElementById(`tab-${ip}`)?.remove();
    document.getElementById(`panel-${ip}`)?.remove();

    delete charts[ip];
    delete names[ip];

    if (activeIP === ip) {
        activeIP = null;
        const next = document.querySelector('#tabs .tab');
        if (next) activateTab(next.id.replace('tab-', ''));
    }

    // remove também do estado local
    for (const g of Object.values(groups)) {
        g.hosts = g.hosts.filter(h => h.ip !== ip);
    }

    await fetch('/remove_ip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip })
    });
}

// =========================
// TABS
// =========================
function activateTab(ip) {
    activeIP = ip;

    document.querySelectorAll('.panel').forEach(p =>
        p.classList.remove('active')
    );

    const panel = document.getElementById(`panel-${ip}`);
    panel.classList.add('active');

    charts[ip]?.resize();
    charts[ip]?.update();
}

// =========================
// UPDATE CHARTS
// =========================
async function updateCharts() {
    const res = await fetch('/data');
    const data = await res.json();

    for (let ip in data) {
        if (!charts[ip]) continue;

        const history = data[ip];
        const last = history[history.length - 1];

        charts[ip].data.labels = history.map(v =>
            new Date(v.ts * 1000).toLocaleTimeString()
        );

        charts[ip].data.datasets[0].data = history.map(v =>
            v.latency === null ? NaN : v.latency
        );

        const tab = document.getElementById(`tab-${ip}`);
        tab.classList.remove('up', 'instavel', 'down');

        if (last.status === 'UP') tab.classList.add('up');
        else if (last.status === 'INSTAVEL') tab.classList.add('instavel');
        else tab.classList.add('down');

        charts[ip].update();
    }
}

setInterval(updateCharts, 2000);

// ENTER = ADD
document.getElementById('ipInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
        e.preventDefault();
        addIP();
    }
});
