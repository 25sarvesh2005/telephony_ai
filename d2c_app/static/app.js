let allProducts = [];
let cart = [];
let allOrders = [];
let selectedOrderIdForNDR = null;
let currentTrackingOrder = null;
let couponDiscountPct = 0;

document.addEventListener('DOMContentLoaded', () => {
    loadProducts();
    loadD2COrders();
    loadAnalytics();
    loadThresholdRiskOrders();
});

// View Switcher
function switchView(viewName) {
    document.querySelectorAll('.d2c-view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));

    const targetView = document.getElementById(`view-${viewName}`);
    const targetTab = document.getElementById(`tab-${viewName}`);

    if (targetView) targetView.classList.add('active');
    if (targetTab) targetTab.classList.add('active');

    if (viewName === 'store' || viewName === 'collection') renderProducts();
    if (viewName === 'logistics' || viewName === 'oms') loadD2COrders();
    if (viewName === 'analytics') {
        loadAnalytics();
        loadThresholdRiskOrders();
    }
    if (viewName === 'tracking') {
        searchTrackingOrder();
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function filterAndSwitchCategory(category) {
    switchView('collection');
    document.querySelectorAll('input[name="cat-filter"]').forEach(cb => {
        cb.checked = (cb.value === category);
    });
    applyFilters();
}

// 1. PRODUCTS & CATALOG
async function loadProducts() {
    try {
        const res = await fetch('/api/d2c/products');
        allProducts = await res.json();
        renderProducts();
    } catch (err) {
        console.error('Error loading products:', err);
    }
}

function renderProducts() {
    renderHomeBestsellers();
    applyFilters();
}

function renderHomeBestsellers() {
    const grid = document.getElementById('home-bestsellers-grid');
    if (!grid) return;
    const featured = allProducts.slice(0, 4);
    grid.innerHTML = featured.map(p => createProductCardHtml(p)).join('');
}

function createProductCardHtml(p) {
    const comparePrice = p.compare_at_price || Math.round(p.price * 1.4);
    const discountPct = Math.round(((comparePrice - p.price) / comparePrice) * 100);

    return `
        <div class="product-card">
            <div class="prod-img-wrap" onclick="openPDPModal('${p.sku}')" style="cursor: pointer;">
                <img src="${p.image_url}" alt="${escapeHtml(p.name)}">
                <span class="discount-badge">${discountPct}% OFF</span>
                <span class="cod-badge"><i class="fa-solid fa-check"></i> COD</span>
            </div>
            <div class="prod-details">
                <span class="prod-category">${p.category}</span>
                <h4 class="prod-title" onclick="openPDPModal('${p.sku}')">${escapeHtml(p.name)}</h4>
                <div class="prod-rating">
                    <i class="fa-solid fa-star"></i>
                    <i class="fa-solid fa-star"></i>
                    <i class="fa-solid fa-star"></i>
                    <i class="fa-solid fa-star"></i>
                    <i class="fa-solid fa-star-half-stroke"></i>
                    <span style="color: var(--text-muted); font-size: 11px;">(4.9 • 120 reviews)</span>
                </div>
                <div class="prod-price-row">
                    <span class="prod-price">₹${p.price.toFixed(2)}</span>
                    <span class="prod-compare-price">₹${comparePrice.toFixed(2)}</span>
                </div>
                <div class="prod-actions-row">
                    <button class="btn btn-secondary btn-sm" onclick="openPDPModal('${p.sku}')" style="flex: 1;">
                        <i class="fa-solid fa-eye"></i> Quick View
                    </button>
                    <button class="btn btn-gold btn-sm" onclick="addToCart('${p.sku}')" style="flex: 1;">
                        <i class="fa-solid fa-bag-shopping"></i> Add to Bag
                    </button>
                </div>
            </div>
        </div>
    `;
}

function updatePriceSlider(val) {
    document.getElementById('price-val').textContent = `₹${parseInt(val).toLocaleString('en-IN')}`;
    applyFilters();
}

function applyFilters() {
    const grid = document.getElementById('collection-products-grid');
    if (!grid) return;

    const query = (document.getElementById('catalog-search')?.value || '').toLowerCase();
    const maxPrice = parseFloat(document.getElementById('price-slider')?.value || 6000);
    const sortVal = document.getElementById('catalog-sort')?.value || 'featured';

    const selectedCategories = Array.from(document.querySelectorAll('input[name="cat-filter"]:checked')).map(cb => cb.value);

    let filtered = allProducts.filter(p => {
        const matchesQuery = p.name.toLowerCase().includes(query) || p.description.toLowerCase().includes(query);
        const matchesCategory = selectedCategories.length === 0 || selectedCategories.includes(p.category);
        const matchesPrice = p.price <= maxPrice;
        return matchesQuery && matchesCategory && matchesPrice;
    });

    if (sortVal === 'price-asc') filtered.sort((a, b) => a.price - b.price);
    if (sortVal === 'price-desc') filtered.sort((a, b) => b.price - a.price);

    if (filtered.length === 0) {
        grid.innerHTML = '<div class="empty-state" style="grid-column: 1/-1;"><p>No products match your selected filters.</p></div>';
        return;
    }

    grid.innerHTML = filtered.map(p => createProductCardHtml(p)).join('');
}

// 2. PRODUCT DETAIL MODAL (PDP)
function openPDPModal(sku) {
    const product = allProducts.find(p => p.sku === sku);
    if (!product) return;

    const comparePrice = product.compare_at_price || Math.round(product.price * 1.4);
    const discountPct = Math.round(((comparePrice - product.price) / comparePrice) * 100);

    const modalContent = document.getElementById('pdp-modal-content');
    modalContent.innerHTML = `
        <div>
            <img class="pdp-gallery-img" src="${product.image_url}" alt="${escapeHtml(product.name)}">
        </div>
        <div class="pdp-info-panel">
            <span class="prod-category">${product.category} • SKU: ${product.sku}</span>
            <h2 style="font-family: var(--font-heading); font-size: 22px;">${escapeHtml(product.name)}</h2>
            <div class="prod-rating">
                <i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i>
                <span style="color: var(--text-muted); font-size: 12px; margin-left: 6px;">4.9 Rating (Verified Buyers)</span>
            </div>
            <div class="prod-price-row">
                <span class="prod-price" style="font-size: 24px; color: var(--color-gold);">₹${product.price.toFixed(2)}</span>
                <span class="prod-compare-price" style="font-size: 14px;">₹${comparePrice.toFixed(2)}</span>
                <span class="discount-badge" style="position: static;">${discountPct}% OFF</span>
            </div>
            <p style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">${escapeHtml(product.description)}</p>

            <div class="pdp-pincode-box">
                <label style="font-weight: 700; color: #FFF;"><i class="fa-solid fa-truck-fast"></i> Estimate Delivery Time:</label>
                <div class="pdp-pincode-row">
                    <input type="text" id="pdp-pincode-input" placeholder="Enter 6-digit Pincode (e.g. 560034)" value="560034">
                    <button class="btn btn-secondary btn-sm" onclick="checkPincodeDelivery()">Check</button>
                </div>
                <div id="pdp-pincode-result" style="margin-top: 6px; color: var(--color-success); font-size: 11px;">
                    <i class="fa-solid fa-circle-check"></i> Express 2-Day Delivery Available via Bluedart Express!
                </div>
            </div>

            <div style="display: flex; gap: 10px; margin-top: 10px;">
                <button class="btn btn-secondary" onclick="addToCart('${product.sku}'); closePDPModal();" style="flex: 1;">
                    <i class="fa-solid fa-bag-shopping"></i> Add to Bag
                </button>
                <button class="btn btn-gold" onclick="addToCart('${product.sku}'); closePDPModal(); toggleCartDrawer();" style="flex: 1;">
                    <i class="fa-solid fa-bolt"></i> Buy Now
                </button>
            </div>
        </div>
    `;

    document.getElementById('pdp-modal').style.display = 'flex';
}

function closePDPModal() {
    document.getElementById('pdp-modal').style.display = 'none';
}

function checkPincodeDelivery() {
    const pin = document.getElementById('pdp-pincode-input').value;
    const res = document.getElementById('pdp-pincode-result');
    if (pin.length === 6) {
        res.innerHTML = `<i class="fa-solid fa-circle-check"></i> Pincode <strong>${pin}</strong> is eligible for Cash on Delivery & 2-Day Bluedart Air shipping!`;
        res.style.color = "var(--color-success)";
    } else {
        res.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Please enter a valid 6-digit Indian pincode.`;
        res.style.color = "var(--color-gold)";
    }
}

// 3. SHOPPING CART & PROMO CODE
function toggleCartDrawer() {
    const drawer = document.getElementById('cart-drawer');
    const backdrop = document.getElementById('cart-drawer-backdrop');
    if (drawer.classList.contains('open')) {
        drawer.classList.remove('open');
        backdrop.style.display = 'none';
    } else {
        drawer.classList.add('open');
        backdrop.style.display = 'block';
        renderCart();
    }
}

function addToCart(sku) {
    const product = allProducts.find(p => p.sku === sku);
    if (!product) return;

    const existing = cart.find(item => item.product.sku === sku);
    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({ product, quantity: 1 });
    }

    updateCartBadge();
    showToast(`Added <strong>${product.name}</strong> to your bag!`);
}

function updateCartQty(sku, delta) {
    const item = cart.find(i => i.product.sku === sku);
    if (!item) return;
    item.quantity += delta;
    if (item.quantity <= 0) {
        cart = cart.filter(i => i.product.sku !== sku);
    }
    renderCart();
    updateCartBadge();
}

function updateCartBadge() {
    const totalCount = cart.reduce((sum, item) => sum + item.quantity, 0);
    document.getElementById('cart-item-count').textContent = totalCount;
}

function applyCoupon() {
    const code = document.getElementById('coupon-code-input').value.trim().toUpperCase();
    if (code === 'AURA10') {
        couponDiscountPct = 0.10;
        showToast('Promo code <strong>AURA10</strong> applied: 10% OFF!');
        renderCart();
    } else {
        showToast('Invalid promo code. Try <strong>AURA10</strong>.');
    }
}

function renderCart() {
    const body = document.getElementById('cart-drawer-body');
    const subtotalElem = document.getElementById('cart-subtotal');
    const discountRow = document.getElementById('coupon-discount-row');
    const discountVal = document.getElementById('coupon-discount-val');
    const freeShippingFill = document.getElementById('free-shipping-fill');
    const freeShippingText = document.getElementById('free-shipping-text');

    if (cart.length === 0) {
        body.innerHTML = '<div class="empty-cart-msg"><i class="fa-solid fa-bag-shopping" style="font-size: 32px; color: var(--text-muted); margin-bottom: 10px; display: block;"></i>Your shopping bag is empty.</div>';
        subtotalElem.textContent = '₹0.00';
        if (discountRow) discountRow.style.display = 'none';
        if (freeShippingFill) freeShippingFill.style.width = '0%';
        return;
    }

    let subtotal = 0;
    body.innerHTML = cart.map(item => {
        const itemTotal = item.product.price * item.quantity;
        subtotal += itemTotal;
        return `
            <div class="cart-item">
                <img src="${item.product.image_url}" alt="${escapeHtml(item.product.name)}">
                <div class="cart-item-details">
                    <div>
                        <h4 style="font-size: 13px; font-weight: 600;">${escapeHtml(item.product.name)}</h4>
                        <span style="font-size: 11px; color: var(--color-gold);">₹${item.product.price.toFixed(2)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div class="cart-qty-ctrl">
                            <button class="qty-btn" onclick="updateCartQty('${item.product.sku}', -1)">-</button>
                            <span style="font-size: 12px; font-weight: 700;">${item.quantity}</span>
                            <button class="qty-btn" onclick="updateCartQty('${item.product.sku}', 1)">+</button>
                        </div>
                        <strong style="font-size: 13px;">₹${itemTotal.toFixed(2)}</strong>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    let finalTotal = subtotal;
    if (couponDiscountPct > 0) {
        const discount = subtotal * couponDiscountPct;
        finalTotal -= discount;
        if (discountRow) {
            discountRow.style.display = 'flex';
            discountVal.textContent = `-₹${discount.toFixed(2)}`;
        }
    } else if (discountRow) {
        discountRow.style.display = 'none';
    }

    subtotalElem.textContent = `₹${finalTotal.toFixed(2)}`;

    // Free shipping threshold ₹1,999
    const threshold = 1999;
    const progress = Math.min(100, Math.round((subtotal / threshold) * 100));
    if (freeShippingFill) freeShippingFill.style.width = `${progress}%`;
    if (freeShippingText) {
        if (subtotal >= threshold) {
            freeShippingText.innerHTML = `<i class="fa-solid fa-circle-check" style="color: var(--color-success);"></i> You have qualified for <strong>FREE Express Shipping</strong>!`;
        } else {
            const diff = threshold - subtotal;
            freeShippingText.textContent = `Add ₹${diff.toFixed(0)} more for FREE Express Shipping!`;
        }
    }
}

// 4. CHECKOUT & CONFETTI
function openCheckoutModal() {
    if (cart.length === 0) {
        alert('Your bag is empty!');
        return;
    }
    toggleCartDrawer();
    document.getElementById('checkout-modal').style.display = 'flex';
}

function closeCheckoutModal() {
    document.getElementById('checkout-modal').style.display = 'none';
}

async function executeCheckout() {
    const btn = document.getElementById('place-order-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Placing order...';

    const name = document.getElementById('chk-name').value;
    const phone = document.getElementById('chk-phone').value;
    const address = document.getElementById('chk-address').value;
    const city = document.getElementById('chk-city').value;
    const pincode = document.getElementById('chk-pincode').value;
    const paymentMethod = document.querySelector('input[name="payment-method"]:checked').value;

    const payload = {
        customer_name: name,
        customer_phone: phone,
        shipping_address: address,
        city: city,
        pincode: pincode,
        payment_method: paymentMethod,
        items: cart.map(i => ({ product_id: i.product.id, quantity: i.quantity, unit_price: i.product.price }))
    };

    try {
        const res = await fetch('/api/d2c/checkout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const order = await res.json();
        closeCheckoutModal();
        cart = [];
        updateCartBadge();

        // Trigger celebratory confetti
        if (typeof confetti === 'function') {
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { y: 0.6 }
            });
        }

        showToast(`🎉 Order <strong>#${order.order_id}</strong> placed successfully!`);
        await loadD2COrders();
        switchView('tracking');
        document.getElementById('tracking-query').value = order.order_id;
        searchTrackingOrder();
    } catch (err) {
        alert('Checkout error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-check"></i> Place D2C Order';
    }
}

// 5. LIVE TRACKING & NDR SELF-RESOLUTION
async function searchTrackingOrder() {
    const orderId = document.getElementById('tracking-query')?.value.trim();
    if (!orderId) return;

    const resultBox = document.getElementById('tracking-result-box');
    resultBox.style.display = 'block';
    resultBox.innerHTML = '<div class="loading-state"><div class="spinner"></div> Fetching live telemetry...</div>';

    try {
        const res = await fetch(`/api/d2c/orders/${orderId}`);
        if (!res.ok) {
            resultBox.innerHTML = `<div class="empty-state"><p>Order <strong>#${escapeHtml(orderId)}</strong> not found. Check Order ID or place a new order.</p></div>`;
            return;
        }
        const data = await res.json();
        currentTrackingOrder = data;
        renderTrackingView(data);
    } catch (err) {
        resultBox.innerHTML = `<div class="empty-state"><p>Could not fetch order details: ${err.message}</p></div>`;
    }
}

function renderTrackingView(data) {
    const resultBox = document.getElementById('tracking-result-box');
    const { order, ndr_tickets, recovery_resolutions } = data;

    const isNDRFailed = order.status === 'DELIVERY_FAILED_NDR' || order.status === 'DELIVERY_FAILED';
    const isDelivered = order.status === 'DELIVERED';
    const isOutForDelivery = order.status === 'OUT_FOR_DELIVERY' || isNDRFailed;
    const isRescheduled = order.status === 'RESCHEDULED';

    resultBox.innerHTML = `
        <div class="tracking-card">
            <div class="tracking-header-grid">
                <div class="tracking-header-item"><label>Order ID</label><strong>#${order.order_id}</strong></div>
                <div class="tracking-header-item"><label>Courier / AWB</label><span>${order.courier_partner} • ${order.tracking_awb}</span></div>
                <div class="tracking-header-item"><label>COD Total</label><span>₹${order.total_amount.toFixed(2)} (${order.payment_method})</span></div>
                <div class="tracking-header-item"><label>Status</label>${getStatusBadgeHtml(order.status)}</div>
            </div>

            <!-- Milestone Progress Bar -->
            <div class="milestones-track">
                <div class="milestone-step done">
                    <div class="milestone-icon"><i class="fa-solid fa-receipt"></i></div>
                    <span>Ordered</span>
                </div>
                <div class="milestone-step done">
                    <div class="milestone-icon"><i class="fa-solid fa-box-archive"></i></div>
                    <span>Packed</span>
                </div>
                <div class="milestone-step ${isOutForDelivery || isDelivered ? 'done' : 'active'}">
                    <div class="milestone-icon"><i class="fa-solid fa-plane-departure"></i></div>
                    <span>In Transit</span>
                </div>
                <div class="milestone-step ${isNDRFailed ? 'failed' : (isDelivered ? 'done' : (isOutForDelivery ? 'active' : ''))}">
                    <div class="milestone-icon"><i class="fa-solid ${isNDRFailed ? 'fa-triangle-exclamation' : 'fa-truck-fast'}"></i></div>
                    <span>${isNDRFailed ? 'NDR Failed' : 'Out for Delivery'}</span>
                </div>
                <div class="milestone-step ${isDelivered ? 'done' : ''}">
                    <div class="milestone-icon"><i class="fa-solid fa-house-circle-check"></i></div>
                    <span>Delivered</span>
                </div>
            </div>

            <!-- Special NDR Alert Card -->
            ${isNDRFailed ? `
            <div class="ndr-alert-card">
                <h4><i class="fa-solid fa-triangle-exclamation"></i> Action Required: Delivery Re-attempt Needed</h4>
                <p>The courier attempted delivery today, but the customer was unavailable. Choose a resolution below to prevent the order from being returned to warehouse:</p>
                <div class="ndr-actions-grid">
                    <button class="btn btn-gold" onclick="rescheduleTrackingOrder('${order.order_id}')">
                        <i class="fa-solid fa-calendar-check"></i> Reschedule for Tomorrow (6 PM)
                    </button>
                    <button class="btn btn-purple" onclick="simulateAIVoiceCall('${order.order_id}', '${order.customer_phone}')">
                        <i class="fa-solid fa-phone-volume"></i> Trigger Live AI Voice Call
                    </button>
                    <button class="btn btn-secondary" onclick="updateTrackingAddress('${order.order_id}')">
                        <i class="fa-solid fa-map-location-dot"></i> Update Delivery Address
                    </button>
                    <button class="btn btn-outline" onclick="cancelTrackingOrder('${order.order_id}')" style="color: #F87171; border-color: rgba(239, 68, 68, 0.4);">
                        <i class="fa-solid fa-ban"></i> Cancel & Return to Origin (RTO)
                    </button>
                </div>
                <div id="ai-call-simulation-box" style="display: none;"></div>
            </div>
            ` : ''}

            <!-- Destination Info -->
            <div style="font-size: 12px; color: var(--text-secondary); background: var(--bg-surface-elevated); padding: 12px; border-radius: var(--radius-sm);">
                <strong><i class="fa-solid fa-location-dot"></i> Delivery Address:</strong> ${escapeHtml(order.shipping_address)}, ${order.city} - ${order.pincode}<br>
                <strong><i class="fa-solid fa-phone"></i> Contact Phone:</strong> ${order.customer_phone}
            </div>
        </div>
    `;
}

async function rescheduleTrackingOrder(orderId) {
    showToast(`Rescheduling delivery for Order #${orderId} to Tomorrow 6:00 PM...`);
    try {
        await fetch('/simulate-call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: orderId,
                scenario: 'reschedule',
                reschedule_datetime: 'Tomorrow at 6:00 PM'
            })
        });
        showToast(`Delivery rescheduled! Courier dispatch updated.`);
        searchTrackingOrder();
        loadD2COrders();
    } catch (err) {
        alert('Reschedule error: ' + err.message);
    }
}

async function simulateAIVoiceCall(orderId, phone) {
    const box = document.getElementById('ai-call-simulation-box');
    if (!box) return;
    box.style.display = 'block';
    box.innerHTML = `
        <div class="audio-wave-box">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 12px; font-weight: 700; color: var(--color-purple);"><i class="fa-solid fa-phone-volume"></i> Outbound Call in Progress to ${phone}...</span>
                <span style="font-size: 11px; color: var(--color-success); font-weight: 600;">LIVE DIALOGUE</span>
            </div>
            <div class="wave-bars">
                <div class="wave-bar"></div><div class="wave-bar"></div><div class="wave-bar"></div>
                <div class="wave-bar"></div><div class="wave-bar"></div><div class="wave-bar"></div>
            </div>
            <div style="margin-top: 10px; font-size: 12px; color: var(--text-primary); background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px;">
                <strong style="color: var(--color-purple);">Mira (AI Agent):</strong> "Hello, calling from Aura Luxe regarding your COD parcel #${orderId}. Would you like to reschedule delivery for tomorrow?"
            </div>
        </div>
    `;

    try {
        await fetch('/trigger-call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: orderId,
                phone_override: phone,
                telephony_provider: 'eigi'
            })
        });
    } catch (e) {}
}

async function updateTrackingAddress(orderId) {
    const newAddr = prompt("Enter updated delivery address & landmark:", "Flat 402, Sunshine Heights, Koramangala 4th Block");
    if (!newAddr) return;
    try {
        await fetch('/simulate-call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: orderId,
                scenario: 'wrong_address',
                updated_address: newAddr
            })
        });
        showToast(`Address updated successfully!`);
        searchTrackingOrder();
        loadD2COrders();
    } catch (err) {
        alert(err.message);
    }
}

async function cancelTrackingOrder(orderId) {
    if (!confirm("Are you sure you want to cancel this order and initiate Return to Origin (RTO)?")) return;
    try {
        await fetch('/simulate-call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: orderId,
                scenario: 'cancel'
            })
        });
        showToast(`Order #${orderId} marked as Cancelled (RTO).`);
        searchTrackingOrder();
        loadD2COrders();
    } catch (err) {
        alert(err.message);
    }
}

// 6. LOGISTICS & OMS
async function loadD2COrders() {
    try {
        const res = await fetch('/api/d2c/orders');
        allOrders = await res.json();
        renderLogisticsTable();
        renderOMSTable();
    } catch (err) {
        console.error('Error loading orders:', err);
    }
}

function renderLogisticsTable() {
    const tbody = document.getElementById('logistics-table-body');
    if (!tbody) return;
    if (allOrders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="loading-state">No active shipments in pipeline. Place an order from the storefront.</td></tr>';
        return;
    }

    tbody.innerHTML = allOrders.map(o => `
        <tr>
            <td>
                <strong style="color: var(--color-gold); font-family: var(--font-mono);">#${o.order_id}</strong>
                <div style="font-size: 10px; color: var(--text-muted);">${o.courier_partner} • ${o.tracking_awb}</div>
            </td>
            <td>
                <div style="font-weight: 600;">${escapeHtml(o.customer_name)}</div>
                <div style="font-size: 11px; color: var(--text-muted);">${o.customer_phone}</div>
            </td>
            <td><strong>₹${o.total_amount.toFixed(2)}</strong> <span style="font-size: 10px; color: var(--text-muted);">${o.payment_method}</span></td>
            <td>${getStatusBadgeHtml(o.status)}</td>
            <td class="text-right">
                <button class="btn btn-secondary btn-sm" onclick="markOutForDelivery('${o.order_id}')" title="Courier out for delivery">
                    <i class="fa-solid fa-truck-fast"></i> Out for Delivery
                </button>
                <button class="btn btn-danger btn-sm" onclick="openNDRModal('${o.order_id}')" title="Trigger delivery failure and AI recovery call">
                    <i class="fa-solid fa-phone-volume"></i> Trigger NDR Call
                </button>
            </td>
        </tr>
    `).join('');
}

function renderOMSTable() {
    const tbody = document.getElementById('oms-table-body');
    if (!tbody) return;
    if (allOrders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-state">No orders found.</td></tr>';
        return;
    }

    tbody.innerHTML = allOrders.map(o => `
        <tr>
            <td><strong style="color: var(--color-gold); font-family: var(--font-mono);">#${o.order_id}</strong></td>
            <td>
                <div style="font-weight: 600;">${escapeHtml(o.customer_name)}</div>
                <div style="font-size: 11px; color: var(--text-muted);">${o.customer_phone} • ${o.city}</div>
            </td>
            <td>${o.items_count} items</td>
            <td><strong>₹${o.total_amount.toFixed(2)}</strong> (${o.payment_method})</td>
            <td>${getStatusBadgeHtml(o.status)}</td>
            <td style="font-size: 11px; color: var(--text-secondary);">${escapeHtml(o.notes || 'Normal fulfillment')}</td>
            <td class="text-right">
                <button class="btn btn-secondary btn-sm" onclick="switchView('tracking'); document.getElementById('tracking-query').value = '${o.order_id}'; searchTrackingOrder();">
                    <i class="fa-solid fa-crosshairs"></i> Track
                </button>
            </td>
        </tr>
    `).join('');
}

function getStatusBadgeHtml(status) {
    switch (status) {
        case 'DELIVERY_FAILED_NDR':
        case 'DELIVERY_FAILED':
            return '<span class="status-badge" style="background: rgba(239, 68, 68, 0.2); color: #FCA5A5; border: 1px solid rgba(239,68,68,0.4);"><i class="fa-solid fa-triangle-exclamation"></i> NDR Failed</span>';
        case 'RESCHEDULED':
            return '<span class="status-badge" style="background: rgba(16, 185, 129, 0.2); color: #6EE7B7; border: 1px solid rgba(16,185,129,0.4);"><i class="fa-solid fa-calendar-check"></i> Rescheduled</span>';
        case 'OUT_FOR_DELIVERY':
            return '<span class="status-badge" style="background: rgba(245, 158, 11, 0.2); color: #FCD34D; border: 1px solid rgba(245,158,11,0.4);"><i class="fa-solid fa-truck-fast"></i> Out for Delivery</span>';
        case 'DELIVERED':
            return '<span class="status-badge" style="background: rgba(16, 185, 129, 0.2); color: #6EE7B7;"><i class="fa-solid fa-check"></i> Delivered</span>';
        case 'CANCELLED_RTO':
            return '<span class="status-badge" style="background: rgba(107, 114, 128, 0.2); color: #9CA3AF;"><i class="fa-solid fa-rotate-left"></i> Cancelled (RTO)</span>';
        default:
            return `<span class="status-badge">${status}</span>`;
    }
}

async function markOutForDelivery(orderId) {
    try {
        await fetch(`/api/d2c/logistics/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId, new_status: 'OUT_FOR_DELIVERY', location: 'Local Delivery Hub' })
        });
        showToast(`Order #${orderId} marked Out for Delivery!`);
        loadD2COrders();
    } catch (err) {
        alert(err.message);
    }
}

function openNDRModal(orderId) {
    selectedOrderIdForNDR = orderId;
    const order = allOrders.find(o => o.order_id === orderId);
    document.getElementById('ndr-order-summary').innerHTML = `
        <strong>Order:</strong> #${order.order_id} (${order.customer_name})<br>
        <strong>Phone:</strong> ${order.customer_phone} | <strong>Amount:</strong> ₹${order.total_amount}
    `;
    document.getElementById('ndr-modal').style.display = 'flex';
}

function closeNDRModal() {
    document.getElementById('ndr-modal').style.display = 'none';
}

async function executeNDRTrigger() {
    const btn = document.getElementById('confirm-ndr-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner"></div> Reporting & Dialing...';

    const reason = document.getElementById('ndr-failure-code').value;
    const remarks = document.getElementById('ndr-remarks').value;
    const provider = document.getElementById('ndr-telephony-provider').value;

    try {
        const res = await fetch('/api/d2c/logistics/ndr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: selectedOrderIdForNDR,
                reason_code: reason,
                remarks: remarks,
                telephony_provider: provider
            })
        });
        const data = await res.json();
        closeNDRModal();
        showToast(`📞 NDR Reported! AI Voice Call Dispatched via ${provider.toUpperCase()}`);
        await loadD2COrders();
        switchView('tracking');
        document.getElementById('tracking-query').value = selectedOrderIdForNDR;
        searchTrackingOrder();
    } catch (err) {
        alert('NDR Trigger error: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-phone-volume"></i> Report Failure & Call Customer';
    }
}

// 7. ANALYTICS & RISK BOT
async function loadAnalytics() {
    try {
        const res = await fetch('/api/d2c/analytics');
        const stats = await res.json();
        document.getElementById('d2c-stat-gmv').textContent = `₹${stats.gmv_inr.toLocaleString('en-IN')}`;
        document.getElementById('d2c-stat-orders').textContent = stats.total_orders;
        document.getElementById('d2c-stat-saved').textContent = `₹${stats.saved_rto_cost_inr.toLocaleString('en-IN')}`;
        document.getElementById('d2c-stat-recovery-rate').textContent = `${stats.recovery_rate_pct}%`;
    } catch (err) {
        console.error('Analytics error:', err);
    }
}

async function loadThresholdRiskOrders() {
    const tbody = document.getElementById('risk-bot-table-body');
    const badge = document.getElementById('risk-flagged-count');
    if (!tbody) return;

    try {
        const res = await fetch('/api/d2c/orders/flagged/all');
        const data = await res.json();
        badge.textContent = `${data.total_flagged} Flagged`;

        if (!data.flagged_orders || data.flagged_orders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading-state" style="color: var(--color-success);"><i class="fa-solid fa-circle-check"></i> No high-risk orders flagged. All COD orders within safe parameters.</td></tr>';
            return;
        }

        tbody.innerHTML = data.flagged_orders.map(item => `
            <tr>
                <td><strong style="color: var(--color-gold); font-family: var(--font-mono);">#${item.order_id}</strong></td>
                <td>
                    <div style="font-weight: 600;">${escapeHtml(item.customer_name)}</div>
                    <div style="font-size: 11px; color: var(--text-muted);">${item.customer_phone}</div>
                </td>
                <td><strong>₹${item.amount.toFixed(2)}</strong></td>
                <td><span style="color: ${item.delivery_attempts >= 3 ? '#F87171' : 'inherit'}; font-weight: 700;">${item.delivery_attempts} Attempt(s)</span></td>
                <td>
                    ${item.risk_reasons.map(r => `<span class="status-badge" style="background: rgba(239, 68, 68, 0.2); color: #FCA5A5; font-size: 10px; margin-right: 4px;">${escapeHtml(r)}</span>`).join('')}
                </td>
                <td style="color: var(--color-gold); font-size: 11px; font-weight: 600;">
                    <i class="fa-solid fa-robot"></i> ${escapeHtml(item.recommended_action)}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading-state">Could not load risk analysis.</td></tr>';
    }
}

// Toast Helper
function showToast(html) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast-msg';
    toast.innerHTML = html;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
