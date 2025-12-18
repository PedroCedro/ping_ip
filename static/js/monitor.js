let charts = {};
let names = {};
let activeIP = null;
let draggedTab = null;

const MAX_HOSTS = 60;


async function addHostFromConfig(name, ip) {
    if (!ip || charts[ip]) return;

    names[ip] = name || ip;

    // TAB
    const tab = document.createElement('div');
    tab.id = `tab-${ip}`;
    tab.className = 'tab up';
    tab.innerText = names[ip];
    tab.title = ip;
    tab.draggable = true;
    tab.onclick = () => activateTab(ip);

    const closeBtn = document.createElement('span');
    closeBtn.innerText = 'x';
    closeBtn.className = 'close';
    closeBtn.onclick = (e) => {
        e.stopPropagation();
        removeIP(ip);
    };
    tab.appendChild(closeBtn);

    document.getElementById('tabs').appendChild(tab);

    // PANEL
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
// ADD IP
// =========================
async function addIP() {
    const nameInput = document.getElementById('nameInput');
    const ipInput = document.getElementById('ipInput');

    const name = nameInput.value.trim();
    const ip = ipInput.value.trim();

    if (!ip || charts[ip]) return;

    if (Object.keys(charts).length >= MAX_HOSTS) {
        alert(`Limite máximo de ${MAX_HOSTS} IPs atingido`);
        return;
    }

    names[ip] = name || ip;

    nameInput.value = '';
    ipInput.value = '';

    // TAB
    const tab = document.createElement('div');
    tab.id = `tab-${ip}`;
    tab.className = 'tab up';
    tab.innerText = names[ip];
    tab.title = ip;
    tab.draggable = true;
    tab.onclick = () => activateTab(ip);

    // BOTÃO X
    const closeBtn = document.createElement('span');
    closeBtn.innerText = '✕';
    closeBtn.className = 'close';
    closeBtn.onclick = (e) => {
        e.stopPropagation();
        removeIP(ip);
    };
    tab.appendChild(closeBtn);

    // DRAG
    tab.addEventListener('dragstart', () => {
        draggedTab = tab;
        tab.classList.add('dragging');
    });

    tab.addEventListener('dragend', () => {
        draggedTab = null;
        tab.classList.remove('dragging');
    });

    tab.addEventListener('dragover', (e) => e.preventDefault());

    tab.addEventListener('drop', (e) => {
        e.preventDefault();
        if (!draggedTab || draggedTab === tab) return;

        const container = document.getElementById('tabs');
        const draggedIndex = [...container.children].indexOf(draggedTab);
        const targetIndex = [...container.children].indexOf(tab);

        if (draggedIndex < targetIndex) {
            container.insertBefore(draggedTab, tab.nextSibling);
        } else {
            container.insertBefore(draggedTab, tab);
        }
    });

    document.getElementById('tabs').appendChild(tab);

    // PANEL
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
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'ms' }
                }
            }
        }
    });

    if (!activeIP) activateTab(ip);

    await fetch('/add_ip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip, name: names[ip] })
    });
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
// UPDATE
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

// =========================
// LOAD HOSTS
// =========================
async function loadHosts() {
    const res = await fetch('/hosts');
    const hosts = await res.json();

    for (const h of hosts) {
        await addHostFromConfig(h.name, h.ip);
    }
}

document.addEventListener('DOMContentLoaded', loadHosts);


// ENTER = ADD
document.getElementById('ipInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
        e.preventDefault();
        addIP();
    }
});
