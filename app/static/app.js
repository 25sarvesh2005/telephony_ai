let allOrders = [];
let selectedOrderId = null;
let currentScenario = 'reschedule';
let activeModalOrderId = null;

document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
});

// Load stats and orders list
async function loadAllData() {
    await Promise.all([fetchStats(), fetchOrders()]);
    if (selectedOrderId) {
        await loadOrderDetail(selectedOrderId);
    }
}


async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const stats = await res.json();
        document.getElementById('stat-failed').textContent = stats.failed_deliveries;
        document.getElementById('stat-rescheduled').textContent = stats.rescheduled_recovered;
        document.getElementById('stat-cancelled').textContent = stats.cancelled_rto;
        document.getElementById('stat-escalated').textContent = stats.human_escalated;
        document.getElementById('stat-rate').textContent = `${stats.recovery_rate_pct}%`;
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
}

async function fetchOrders() {
    try {
        const res = await fetch('/api/orders');
        allOrders = await res.json();
        document.getElementById('orders-count').textContent = allOrders.length;
        renderOrdersTable(allOrders);

        // Auto-select first order if none selected
        if (!selectedOrderId && allOrders.length > 0) {
            selectOrder(allOrders[0].order_id);
        }
    } catch (err) {
        console.error('Failed to load orders:', err);
        document.getElementById('orders-table-body').innerHTML = `
            <tr><td colspan="6" class="loading-state" style="color: var(--color-danger)">
                <i class="fa-solid fa-circle-exclamation"></i> Error loading orders
            </td></tr>
        `;
    }
}

function renderOrdersTable(orders) {
    const tbody = document.getElementById('orders-table-body');
    if (orders.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="6" class="loading-state">
                No failed orders found. Click "Seed Orders" to generate realistic test cases.
            </td></tr>
        `;
        return;
    }

    tbody.innerHTML = orders.map(order => {
        const isSelected = order.order_id === selectedOrderId;
        const statusBadge = getStatusBadge(order.status);
        return `
            <tr class="${isSelected ? 'selected' : ''}" onclick="selectOrder('${order.order_id}')">
                <td>
                    <strong style="font-family: var(--font-mono); color: var(--text-primary);">${order.order_id}</strong>
                    <div style="font-size: 11px; color: var(--text-muted);">${order.city || 'Standard Delivery'}</div>
                </td>
                <td>
                    <div style="font-weight: 600;">${escapeHtml(order.customer_name)}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">${order.customer_phone}</div>
                </td>
                <td>
                    <strong>${order.currency} ${order.amount.toFixed(2)}</strong>
                    <div style="font-size: 10px; color: var(--text-muted);">${order.payment_method}</div>
                </td>
                <td>
                    <span style="font-weight: 600; color: ${order.delivery_attempts >= 3 ? '#F87171' : 'var(--text-primary)'}">
                        ${order.delivery_attempts} attempt${order.delivery_attempts > 1 ? 's' : ''}
                    </span>
                </td>
                <td>${statusBadge}</td>
                <td class="text-right" onclick="event.stopPropagation()">
                    <button class="btn btn-primary btn-sm" title="Run Simulator Webhook" onclick="openSimulatorModal('${order.order_id}')">
                        <i class="fa-solid fa-bolt"></i> Sim Call
                    </button>
                    <button class="btn btn-secondary btn-sm" title="Trigger eigi.ai Outbound Call" onclick="openTriggerModal('${order.order_id}')">
                        <i class="fa-solid fa-phone"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function getStatusBadge(status) {
    switch (status) {
        case 'DELIVERY_FAILED':
            return '<span class="status-badge status-failed"><i class="fa-solid fa-circle-exclamation"></i> Failed</span>';
        case 'RESCHEDULED':
            return '<span class="status-badge status-rescheduled"><i class="fa-solid fa-calendar-check"></i> Rescheduled</span>';
        case 'CANCELLED_RTO':
            return '<span class="status-badge status-cancelled"><i class="fa-solid fa-arrow-rotate-left"></i> Cancelled (RTO)</span>';
        case 'HUMAN_ESCALATION':
            return '<span class="status-badge status-escalated"><i class="fa-solid fa-headset"></i> Escalated</span>';
        case 'ADDRESS_UPDATE_REQUIRED':
            return '<span class="status-badge status-address"><i class="fa-solid fa-location-dot"></i> Address Update</span>';
        case 'CALL_IN_PROGRESS':
            return '<span class="status-badge status-calling"><i class="fa-solid fa-phone-volume"></i> Calling...</span>';
        case 'CALL_RETRY_SCHEDULED':
            return '<span class="status-badge status-calling"><i class="fa-solid fa-clock-rotate-left"></i> Retry Queued</span>';
        default:
            return `<span class="status-badge">${status}</span>`;
    }
}

async function selectOrder(orderId) {
    selectedOrderId = orderId;
    renderOrdersTable(allOrders);
    await loadOrderDetail(orderId);
}

async function loadOrderDetail(orderId) {
    const detailBody = document.getElementById('detail-body');
    const quickActions = document.getElementById('quick-panel-actions');
    const title = document.getElementById('detail-title');

    title.textContent = `Order Details #${orderId}`;
    quickActions.innerHTML = `
        <button class="btn btn-secondary btn-sm" onclick="resetOrder('${orderId}')" title="Reset order state">
            <i class="fa-solid fa-rotate-left"></i> Reset
        </button>
        <button class="btn btn-primary btn-sm" onclick="openSimulatorModal('${orderId}')">
            <i class="fa-solid fa-bolt"></i> Sim Call
        </button>
        <button class="btn btn-success btn-sm" onclick="openTriggerModal('${orderId}')">
            <i class="fa-solid fa-phone"></i> Call
        </button>
    `;

    try {
        const res = await fetch(`/api/orders/${orderId}`);
        if (!res.ok) throw new Error('Order not found');
        const data = await res.json();
        const { order, call_logs, resolutions } = data;

        let callLogsHtml = '<p style="color: var(--text-muted); font-size: 13px;">No voice calls recorded yet for this order. Click "Sim Call" or "Call" to start.</p>';
        if (call_logs && call_logs.length > 0) {
            callLogsHtml = call_logs.map(log => {
                const intent = log.extracted_intent || {};
                return `
                    <div class="info-card" style="margin-bottom: 12px;">
                        <div class="info-card-header">
                            <h4><i class="fa-solid fa-phone"></i> Call ${log.call_id}</h4>
                            <span class="count-badge">${log.call_outcome.toUpperCase()}</span>
                        </div>
                        <div class="info-grid">
                            <div class="info-item">
                                <label>Duration</label>
                                <span>${log.duration_seconds} seconds</span>
                            </div>
                            <div class="info-item">
                                <label>Customer Intent</label>
                                <span style="color: #A78BFA; font-weight: 600;">${(intent.customer_intent || 'unclear').toUpperCase()}</span>
                            </div>
                        </div>

                        ${log.recording_url ? `
                        <div class="audio-player-box">
                            <i class="fa-solid fa-play" style="color: var(--color-primary);"></i>
                            <audio controls preload="none" src="${log.recording_url}"></audio>
                        </div>
                        ` : ''}

                        <div style="margin-top: 10px;">
                            <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;"><i class="fa-solid fa-comments"></i> Voice Conversation Transcript:</label>
                            ${formatTranscriptToDialogue(log.transcript)}
                        </div>

                        <div style="margin-top: 10px;">
                            <label style="font-size: 11px; color: var(--text-muted); display: block; margin-bottom: 4px;"><i class="fa-solid fa-brain"></i> Extracted Structured Intent (JSON):</label>
                            <pre class="code-block">${JSON.stringify(intent, null, 2)}</pre>
                        </div>
                    </div>
                `;
            }).join('');
        }

        let resolutionsHtml = '<p style="color: var(--text-muted); font-size: 13px;">No operational actions executed yet.</p>';
        if (resolutions && resolutions.length > 0) {
            resolutionsHtml = resolutions.map(res => {
                return `
                    <div class="timeline-item">
                        <div class="timeline-title">${escapeHtml(res.decided_action.toUpperCase())} <span class="count-badge" style="color: #34D399;">${res.status}</span></div>
                        <div class="timeline-desc">${escapeHtml(res.outcome || '')}</div>
                        <div class="timeline-time"><i class="fa-regular fa-clock"></i> ${new Date(res.executed_at).toLocaleString()}</div>
                    </div>
                `;
            }).join('');
        }

        detailBody.innerHTML = `
            <!-- Order Summary Card -->
            <div class="info-card">
                <div class="info-card-header">
                    <h4><i class="fa-solid fa-box"></i> Order Information</h4>
                    ${getStatusBadge(order.status)}
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <label>Customer Name</label>
                        <span>${escapeHtml(order.customer_name)}</span>
                    </div>
                    <div class="info-item">
                        <label>Phone Number</label>
                        <span>${order.customer_phone}</span>
                    </div>
                    <div class="info-item">
                        <label>Order Amount</label>
                        <span>${order.currency} ${order.amount.toFixed(2)} (${order.payment_method})</span>
                    </div>
                    <div class="info-item">
                        <label>Delivery Attempts</label>
                        <span>${order.delivery_attempts}</span>
                    </div>
                </div>
                <div style="margin-top: 12px;">
                    <div class="info-item">
                        <label>Delivery Address</label>
                        <span>${escapeHtml(order.delivery_address || 'N/A')}, ${escapeHtml(order.city || '')}</span>
                    </div>
                </div>
                ${order.notes ? `
                <div style="margin-top: 10px; font-size: 12px; color: #FBBF24;">
                    <label style="color: var(--text-muted); font-size: 11px; display: block;">Latest Note</label>
                    ${escapeHtml(order.notes)}
                </div>
                ` : ''}
            </div>

            <!-- Operational Resolutions -->
            <div class="info-card">
                <div class="info-card-header">
                    <h4><i class="fa-solid fa-gears"></i> Operations & Resolution Log</h4>
                </div>
                <div>${resolutionsHtml}</div>
            </div>

            <!-- Call Logs & Transcripts -->
            <div class="info-card">
                <div class="info-card-header">
                    <h4><i class="fa-solid fa-wave-square"></i> Voice Call Transcripts & Telephony Logs</h4>
                </div>
                <div>${callLogsHtml}</div>
            </div>
        `;
    } catch (err) {
        detailBody.innerHTML = `<div class="loading-state" style="color: var(--color-danger)">Error loading order details: ${err.message}</div>`;
    }
}

function filterOrders() {
    const q = document.getElementById('order-search').value.toLowerCase().trim();
    if (!q) {
        renderOrdersTable(allOrders);
        return;
    }
    const filtered = allOrders.filter(o => 
        o.order_id.toLowerCase().includes(q) ||
        o.customer_name.toLowerCase().includes(q) ||
        o.customer_phone.includes(q) ||
        (o.city && o.city.toLowerCase().includes(q))
    );
    renderOrdersTable(filtered);
}

// Modal Handlers
function openSimulatorModal(orderId) {
    activeModalOrderId = orderId;
    const order = allOrders.find(o => o.order_id === orderId);
    if (!order) return;

    document.getElementById('modal-order-summary').innerHTML = `
        <strong>Simulating recovery call for Order #${order.order_id}</strong><br>
        Customer: ${escapeHtml(order.customer_name)} | Amount: ${order.currency} ${order.amount} (${order.payment_method})
    `;
    selectScenario('reschedule');
    document.getElementById('simulator-modal').style.display = 'flex';
}

function closeSimulatorModal() {
    document.getElementById('simulator-modal').style.display = 'none';
}

function selectScenario(scenario) {
    currentScenario = scenario;
    document.querySelectorAll('.scenario-chips .chip').forEach(c => c.classList.remove('active'));
    event.currentTarget?.classList?.add('active');

    const reschedGroup = document.getElementById('reschedule-input-group');
    const addrGroup = document.getElementById('address-input-group');

    reschedGroup.style.display = (scenario === 'reschedule') ? 'block' : 'none';
    addrGroup.style.display = (scenario === 'wrong_address') ? 'block' : 'none';
}

async function executeSimulation() {
    const btn = document.getElementById('run-simulation-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Running webhook pipeline...';

    const rescheduleDt = document.getElementById('custom-reschedule-time').value;
    const updatedAddr = document.getElementById('custom-updated-address').value;

    try {
        const res = await fetch('/simulate-call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: activeModalOrderId,
                scenario: currentScenario,
                reschedule_datetime: rescheduleDt,
                updated_address: updatedAddr
            })
        });
        const data = await res.json();
        closeSimulatorModal();
        await loadAllData();
        await selectOrder(activeModalOrderId);
    } catch (err) {
        alert('Simulation failed: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-play"></i> Run Simulation & Webhook Flow';
    }
}

function openTriggerModal(orderId) {
    activeModalOrderId = orderId;
    const order = allOrders.find(o => o.order_id === orderId);
    if (!order) return;

    document.getElementById('trigger-order-summary').innerHTML = `
        <strong>Order:</strong> #${order.order_id} (${order.customer_name})<br>
        <strong>Amount:</strong> ${order.currency} ${order.amount} | <strong>Attempts:</strong> ${order.delivery_attempts}
    `;
    document.getElementById('trigger-phone-override').value = order.customer_phone;
    document.getElementById('trigger-modal').style.display = 'flex';
}

function closeTriggerModal() {
    document.getElementById('trigger-modal').style.display = 'none';
}

async function executeTriggerCall() {
    const btn = document.getElementById('confirm-trigger-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Dialing eigi.ai...';

    const phone = document.getElementById('trigger-phone-override').value;

    try {
        const res = await fetch('/trigger-call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: activeModalOrderId,
                phone_override: phone || undefined
            })
        });
        const data = await res.json();
        closeTriggerModal();
        await loadAllData();
        await selectOrder(activeModalOrderId);
    } catch (err) {
        alert('Outbound call failed: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-phone"></i> Start Outbound Call';
    }
}

async function resetOrder(orderId) {
    try {
        await fetch(`/api/orders/${orderId}/reset`, { method: 'POST' });
        await loadAllData();
        await selectOrder(orderId);
    } catch (err) {
        console.error('Reset failed:', err);
    }
}

async function seedSampleOrders() {
    const btn = document.getElementById('seed-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Seeding...';

    const samples = [
        {
            order_id: "ORD-9481",
            customer_name: "Rahul Sharma",
            customer_phone: "+919876543210",
            amount: 2499.00,
            currency: "INR",
            payment_method: "COD",
            delivery_attempts: 1,
            delivery_address: "Flat 204, Green Glen Layout, Bellandur",
            city: "Bengaluru",
            notes: "Courier: Customer not available at residence."
        },
        {
            order_id: "ORD-8712",
            customer_name: "Priya Nair",
            customer_phone: "+919812345678",
            amount: 1850.00,
            currency: "INR",
            payment_method: "COD",
            delivery_attempts: 1,
            delivery_address: "House 14, 5th Main, Indiranagar",
            city: "Bengaluru",
            notes: "Courier: Door locked / phone not reachable."
        },
        {
            order_id: "ORD-6204",
            customer_name: "Vikram Malhotra",
            customer_phone: "+919700112233",
            amount: 4999.00,
            currency: "INR",
            payment_method: "COD",
            delivery_attempts: 2,
            delivery_address: "Tower B, Apt 1102, Hiranandani Estate",
            city: "Mumbai",
            notes: "Courier: Delivery refused - customer requested later date."
        },
        {
            order_id: "ORD-5190",
            customer_name: "Ananya Deshmukh",
            customer_phone: "+919833445566",
            amount: 1290.00,
            currency: "INR",
            payment_method: "COD",
            delivery_attempts: 1,
            delivery_address: "Plot 88, Baner Road",
            city: "Pune",
            notes: "Courier: Incorrect building number."
        },
        {
            order_id: "ORD-3042",
            customer_name: "Karan Johar",
            customer_phone: "+919988776655",
            amount: 8900.00,
            currency: "INR",
            payment_method: "COD",
            delivery_attempts: 3,
            delivery_address: "Sea Mist Villa, Bandra West",
            city: "Mumbai",
            notes: "High value COD - 3 failed delivery attempts."
        }
    ];

    for (const s of samples) {
        try {
            await fetch('/api/orders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(s)
            });
        } catch (e) {
            // ignore duplicate seed
        }
    }

    await loadAllData();
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-database"></i> Seed Orders';
}

async function syncLiveEigiCalls() {
    const btn = document.getElementById('sync-calls-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner"></div> Syncing...';
    }
    try {
        const res = await fetch('/api/sync-calls', { method: 'POST' });
        const data = await res.json();
        await loadAllData();
    } catch (err) {
        console.error('Error syncing live calls:', err);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Sync Live Calls';
        }
    }
}

function formatTranscriptToDialogue(transcript) {
    if (!transcript) return '<div class="transcript-bubble">No transcript available.</div>';
    const lines = transcript.split('\n').filter(l => l.trim().length > 0);
    const messages = [];

    lines.forEach(line => {
        if (line.toLowerCase().startsWith('agent:') || line.toLowerCase().startsWith('assistant:')) {
            messages.push({ role: 'agent', speaker: 'Mira (AI Recovery Agent)', content: line.substring(line.indexOf(':') + 1).trim() });
        } else if (line.toLowerCase().startsWith('customer:') || line.toLowerCase().startsWith('user:')) {
            messages.push({ role: 'customer', speaker: 'Customer', content: line.substring(line.indexOf(':') + 1).trim() });
        } else {
            messages.push({ role: 'agent', speaker: 'Voice AI Engine', content: line });
        }
    });

    return `
        <div class="chat-dialogue">
            ${messages.map(m => `
                <div class="chat-msg ${m.role}">
                    <div class="chat-avatar"><i class="fa-solid ${m.role === 'agent' ? 'fa-robot' : 'fa-user'}"></i></div>
                    <div class="chat-content-bubble">
                        <span class="chat-speaker">${m.speaker}</span>
                        ${escapeHtml(m.content)}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}


