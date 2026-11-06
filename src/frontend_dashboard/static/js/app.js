/**
 * O3 Executive Frontend Application Logic
 *
 * Implements pure vanilla JavaScript client interacting with the backend ETL
 * analytics and Ask O3 conversational assistant APIs.
 */

// Global Application State
let currentAuthenticatedUser = null;
let currentActiveCompanyId = null;
let currentActiveCompanyName = "Shree Polychem";
let currentSelectedPeriod = "mtd";
let currentCustomStart = null;
let currentCustomEnd = null;
let isMobileDrawerExpanded = false;

// ─── Authentication & Bootstrapping ─────────────────────────────────────────────

async function initializeDashboardApplication() {
    const storedAuthToken = localStorage.getItem("o3_token");
    if (!storedAuthToken) {
        window.location.href = "/login";
        return;
    }

    try {
        // Verify token and retrieve user profile
        const profileResponse = await fetch("/api/v1/auth/me", {
            headers: {
                "Authorization": `Bearer ${storedAuthToken}`,
                "Accept": "application/json"
            }
        });

        if (!profileResponse.ok) {
            // Token expired or invalid
            localStorage.removeItem("o3_token");
            localStorage.removeItem("o3_user");
            window.location.href = "/login";
            return;
        }

        const profileData = await profileResponse.json();
        currentAuthenticatedUser = profileData.user;

        // Set user avatar initials
        const userFullName = currentAuthenticatedUser.full_name || "Manoj Kumar";
        const nameParts = userFullName.trim().split(" ");
        const initials = nameParts.length >= 2
            ? (nameParts[0][0] + nameParts[1][0]).toUpperCase()
            : userFullName.substring(0, 2).toUpperCase();

        const avatarElements = document.querySelectorAll(".user-avatar-initials");
        avatarElements.forEach(el => el.textContent = initials);

        // Parse accessible companies (supports [{company_id, company_name}] and ["guid"])
        const accessibleCompanies = currentAuthenticatedUser.accessible_companies || [];
        availableCompanies = accessibleCompanies.map(c => {
            if (typeof c === "object" && c !== null) {
                return {
                    id: c.company_id,
                    name: c.company_name || c.company_id,
                };
            }
            return { id: String(c), name: String(c) };
        });

        // Determine active company: check saved preference in localStorage or default to first
        const savedCompanyId = localStorage.getItem("o3_active_company_id");
        const matchedSaved = availableCompanies.find(c => c.id === savedCompanyId);
        if (matchedSaved) {
            currentActiveCompanyId = matchedSaved.id;
            currentActiveCompanyName = matchedSaved.name;
        } else if (availableCompanies.length > 0) {
            currentActiveCompanyId = availableCompanies[0].id;
            currentActiveCompanyName = availableCompanies[0].name;
            localStorage.setItem("o3_active_company_id", currentActiveCompanyId);
        }

        // Update company display names and ID subtext immediately
        if (currentActiveCompanyName) {
            const compElements = document.querySelectorAll(".company-display-name");
            compElements.forEach(el => el.textContent = currentActiveCompanyName);
            const answeringLabel = document.getElementById("answering-company-label");
            if (answeringLabel) answeringLabel.textContent = `Answering for ${currentActiveCompanyName}`;
        }
        updateCompanyIdSubtext();

        applySyncPausedState();

        // Load sync status, overview KPIs, and single-thread chat
        await refreshCompanySyncStatus();
        await loadExecutiveOverviewMetrics(currentSelectedPeriod);
        await loadSingleThreadChatHistory();

    } catch (err) {
        console.error("Dashboard initialization error:", err);
    }
}

// ─── Analytics & KPI Overview Loading ───────────────────────────────────────────

const PERIOD_CHIP_BASE = "period-chip shrink-0 whitespace-nowrap rounded-full px-4 py-2 text-xs sm:text-sm font-bold border transition-all ";
const PERIOD_CHIP_ACTIVE = "bg-gradient-to-r from-indigo-600 to-violet-600 text-white border-transparent shadow-md shadow-indigo-500/30";
const PERIOD_CHIP_IDLE = "bg-white/80 text-slate-600 border-slate-200 hover:border-indigo-300 hover:text-indigo-600";

function updatePeriodChips(selectedPeriod) {
    document.querySelectorAll("#period-chips .period-chip").forEach(chip => {
        chip.className = PERIOD_CHIP_BASE + (chip.dataset.period === selectedPeriod ? PERIOD_CHIP_ACTIVE : PERIOD_CHIP_IDLE);
    });
}

function selectPeriod(selectedPeriod) {
    const select = document.getElementById("period-dropdown");
    if (select) select.value = selectedPeriod;
    handlePeriodSelectionChange(selectedPeriod);
}

function handlePeriodSelectionChange(selectedPeriod) {
    updatePeriodChips(selectedPeriod);
    const customDateContainer = document.getElementById("custom-date-container");
    if (selectedPeriod === "custom") {
        if (customDateContainer) {
            customDateContainer.classList.remove("hidden");
            const startInput = document.getElementById("custom-start-date");
            const endInput = document.getElementById("custom-end-date");
            const now = new Date();
            const yearStr = now.getFullYear();
            const monthStr = String(now.getMonth() + 1).padStart(2, "0");
            const dayStr = String(now.getDate()).padStart(2, "0");

            if (startInput && !startInput.value) {
                startInput.value = `${yearStr}-${monthStr}-01`;
            }
            if (endInput && !endInput.value) {
                endInput.value = `${yearStr}-${monthStr}-${dayStr}`;
            }
        }
    } else {
        if (customDateContainer) {
            customDateContainer.classList.add("hidden");
        }
        loadExecutiveOverviewMetrics(selectedPeriod);
    }
}

async function applyCustomDateRange() {
    const startInput = document.getElementById("custom-start-date");
    const endInput = document.getElementById("custom-end-date");

    const startDate = startInput ? startInput.value : null;
    const endDate = endInput ? endInput.value : null;

    if (!startDate || !endDate) {
        alert("Please select both a start date and an end date.");
        return;
    }

    await loadExecutiveOverviewMetrics("custom", startDate, endDate);
}

async function loadExecutiveOverviewMetrics(periodPreset = "mtd", customStart = null, customEnd = null) {
    currentSelectedPeriod = periodPreset;
    currentCustomStart = periodPreset === "custom" ? customStart : null;
    currentCustomEnd = periodPreset === "custom" ? customEnd : null;
    const storedAuthToken = localStorage.getItem("o3_token");
    setKpiLoading(true);

    let apiUrl = `/api/v1/analytics/overview?period=${encodeURIComponent(periodPreset)}`;
    if (customStart && customEnd) {
        apiUrl += `&start_date=${encodeURIComponent(customStart)}&end_date=${encodeURIComponent(customEnd)}`;
    }
    if (currentActiveCompanyId) {
        apiUrl += `&company_id=${encodeURIComponent(currentActiveCompanyId)}`;
    }

    try {
        const response = await fetch(apiUrl, {
            headers: {
                "Authorization": `Bearer ${storedAuthToken}`,
                "Accept": "application/json"
            }
        });

        if (!response.ok) {
            throw new Error(`Analytics API returned HTTP ${response.status}`);
        }

        const overviewData = await response.json();
        renderDashboardOverview(overviewData);

    } catch (error) {
        console.error("Failed to load overview metrics:", error);
    } finally {
        setKpiLoading(false);
    }
}

function renderDashboardOverview(overviewData) {
    if (!overviewData) return;

    // Update Company Name and Answering label
    if (overviewData.company_name) {
        currentActiveCompanyName = overviewData.company_name;
        const compElements = document.querySelectorAll(".company-display-name");
        compElements.forEach(el => el.textContent = overviewData.company_name);
        const answeringLabel = document.getElementById("answering-company-label");
        if (answeringLabel) answeringLabel.textContent = `Answering for ${overviewData.company_name}`;
        syncCompanyList();
    }
    updateCompanyIdSubtext();

    // Update Greeting
    const greetingTitleEl = document.getElementById("executive-greeting-title");
    if (greetingTitleEl) greetingTitleEl.textContent = overviewData.greeting_title || "Good morning.";

    const greetingSubtitleEl = document.getElementById("executive-greeting-subtitle");
    if (greetingSubtitleEl) greetingSubtitleEl.innerHTML = colorizeSummary(overviewData.greeting_subtitle || "");

    renderSummaryInsights(overviewData.insights);

    const summaryPeriodEl = document.getElementById("executive-summary-period");
    if (summaryPeriodEl) summaryPeriodEl.textContent = overviewData.period_label ? `· ${overviewData.period_label}` : "";

    const rangeLabelEl = document.getElementById("period-range-label");
    if (rangeLabelEl && overviewData.period_label) rangeLabelEl.textContent = overviewData.period_label;

    // Update Date Pill & Dropdown Label
    if (currentSelectedPeriod === "mtd") {
        const datePillEl = document.getElementById("selected-period-label");
        if (datePillEl && overviewData.period_label) {
            datePillEl.textContent = overviewData.period_label;
        }
    } else if (currentSelectedPeriod === "custom") {
        const customOpt = document.querySelector('#period-dropdown option[value="custom"]');
        if (customOpt && overviewData.period_label) {
            customOpt.textContent = `Custom (${overviewData.period_label})`;
        }
    }

    // Update 4 KPIs
    const kpis = overviewData.kpis || {};

    // 1. Sales
    if (kpis.sales) {
        const parts = splitCurrencyAndUnit(kpis.sales.formatted_value);
        animateKpiValue(document.getElementById("kpi-sales-value"), parts.value);
        document.getElementById("kpi-sales-unit").textContent = parts.unit;

        const trendEl = document.getElementById("kpi-sales-trend");
        const dirSymbol = kpis.sales.delta_direction === "up" ? "↑" : "↓";
        trendEl.textContent = `${dirSymbol} ${Math.abs(kpis.sales.delta_pct)}% ${kpis.sales.prior_label}`;
        trendEl.className = trendPillClass(kpis.sales.delta_direction);
    }

    // 2. Collections
    if (kpis.collections) {
        const parts = splitCurrencyAndUnit(kpis.collections.formatted_value);
        animateKpiValue(document.getElementById("kpi-collections-value"), parts.value);
        document.getElementById("kpi-collections-unit").textContent = parts.unit;

        const trendEl = document.getElementById("kpi-collections-trend");
        const dirSymbol = kpis.collections.delta_direction === "up" ? "↑" : "↓";
        trendEl.textContent = `${dirSymbol} ${Math.abs(kpis.collections.delta_pct)}% ${kpis.collections.prior_label}`;
        trendEl.className = trendPillClass(kpis.collections.delta_direction);
    }

    // 3. Receivables
    if (kpis.receivables) {
        const parts = splitCurrencyAndUnit(kpis.receivables.formatted_value);
        animateKpiValue(document.getElementById("kpi-receivables-value"), parts.value);
        document.getElementById("kpi-receivables-unit").textContent = parts.unit;
        document.getElementById("kpi-receivables-asof").textContent = kpis.receivables.as_of_label || overviewData.as_of_date_label || "";
    }

    // 4. Purchases
    if (kpis.purchases) {
        const parts = splitCurrencyAndUnit(kpis.purchases.formatted_value);
        animateKpiValue(document.getElementById("kpi-purchases-value"), parts.value);
        document.getElementById("kpi-purchases-unit").textContent = parts.unit;

        const trendEl = document.getElementById("kpi-purchases-trend");
        const dirSymbol = kpis.purchases.delta_direction === "up" ? "↑" : "↓";
        trendEl.textContent = `${dirSymbol} ${Math.abs(kpis.purchases.delta_pct)}% ${kpis.purchases.prior_label}`;
        trendEl.className = trendPillClass(kpis.purchases.delta_direction);
    }

    // 5. Inventory
    if (kpis.inventory) {
        const parts = splitCurrencyAndUnit(kpis.inventory.formatted_value);
        animateKpiValue(document.getElementById("kpi-inventory-value"), parts.value);
        document.getElementById("kpi-inventory-unit").textContent = parts.unit;
        document.getElementById("kpi-inventory-items").textContent = `${kpis.inventory.total_items} items`;
        document.getElementById("kpi-inventory-instock").textContent = `${kpis.inventory.in_stock_count} in stock`;
        document.getElementById("kpi-inventory-oos").textContent = `${kpis.inventory.out_of_stock_count} out of stock`;
    }
}

async function openInventoryModal() {
    const modal = document.getElementById("inventory-modal");
    const body = document.getElementById("inventory-modal-body");
    const subtitle = document.getElementById("inventory-modal-subtitle");
    if (!modal || !body) return;

    modal.classList.remove("hidden");
    subtitle.textContent = currentActiveCompanyName || "";
    body.innerHTML = '<p class="text-sm text-slate-500">Loading inventory…</p>';

    let apiUrl = "/api/v1/analytics/inventory?limit=5";
    if (currentActiveCompanyId) {
        apiUrl += `&company_id=${encodeURIComponent(currentActiveCompanyId)}`;
    }

    try {
        const response = await fetch(apiUrl, {
            headers: {
                "Authorization": `Bearer ${localStorage.getItem("o3_token")}`,
                "Accept": "application/json"
            }
        });
        if (!response.ok) throw new Error(`Inventory API returned HTTP ${response.status}`);
        renderInventoryModal(await response.json());
    } catch (error) {
        console.error("Failed to load inventory details:", error);
        body.innerHTML = '<p class="text-sm text-rose-600">Could not load inventory details. Please try again.</p>';
    }
}

function closeInventoryModal() {
    const modal = document.getElementById("inventory-modal");
    if (modal) modal.classList.add("hidden");
}

document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        closeInventoryModal();
        closeKpiModal();
    }
});

// ─── KPI detail popups (sales / collections / purchases / receivables) ─────────

let kpiModalRequestId = 0;

async function openKpiModal(kpi) {
    const modal = document.getElementById("kpi-modal");
    const body = document.getElementById("kpi-modal-body");
    if (!modal || !body) return;

    const requestId = ++kpiModalRequestId;
    const titles = { sales: "Sales", collections: "Collections", purchases: "Purchases", receivables: "Receivables" };
    document.getElementById("kpi-modal-title").textContent = titles[kpi] || "Details";
    document.getElementById("kpi-modal-subtitle").textContent = currentActiveCompanyName || "";
    document.getElementById("kpi-modal-ask-btn").onclick = () => {
        closeKpiModal();
        handleKpiCardClick(kpi);
    };
    body.innerHTML = '<p class="text-sm text-slate-500">Loading details…</p>';
    modal.classList.remove("hidden");

    let apiUrl = `/api/v1/analytics/kpi-details?kpi=${encodeURIComponent(kpi)}&period=${encodeURIComponent(currentSelectedPeriod)}&limit=5`;
    if (currentCustomStart && currentCustomEnd) {
        apiUrl += `&start_date=${encodeURIComponent(currentCustomStart)}&end_date=${encodeURIComponent(currentCustomEnd)}`;
    }
    if (currentActiveCompanyId) {
        apiUrl += `&company_id=${encodeURIComponent(currentActiveCompanyId)}`;
    }

    try {
        const response = await fetch(apiUrl, {
            headers: {
                "Authorization": `Bearer ${localStorage.getItem("o3_token")}`,
                "Accept": "application/json"
            }
        });
        if (!response.ok) throw new Error(`KPI details API returned HTTP ${response.status}`);
        const data = await response.json();
        if (requestId !== kpiModalRequestId) return; // a newer popup was opened meanwhile
        renderKpiModal(data);
    } catch (error) {
        console.error(`Failed to load ${kpi} details:`, error);
        if (requestId === kpiModalRequestId) {
            body.innerHTML = '<p class="text-sm text-rose-600">Could not load details. Please try again.</p>';
        }
    }
}

function closeKpiModal() {
    kpiModalRequestId++;
    const modal = document.getElementById("kpi-modal");
    if (modal) modal.classList.add("hidden");
}

function kpiTrendHtml(trend) {
    const points = (trend && trend.points) || [];
    if (!points.length) return "";
    const max = Math.max(...points.map(p => p.value), 0);
    const bars = points.map(p => {
        const pct = max > 0 ? Math.max(2, Math.round((p.value / max) * 100)) : 2;
        return `<div class="flex-1 min-w-[3px] bg-indigo-400/80 hover:bg-indigo-600 rounded-t transition-colors"
                     style="height:${pct}%" title="${escapeHtml(p.label)}: ${escapeHtml(p.formatted)}"></div>`;
    }).join("");
    const first = escapeHtml(points[0].label);
    const last = escapeHtml(points[points.length - 1].label);
    return `
        <section>
            <h4 class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">${escapeHtml(trend.title || "Trend")}</h4>
            <div class="flex items-end gap-[2px] h-28 rounded-2xl bg-slate-50 px-3 pt-3">${bars}</div>
            <div class="flex justify-between text-[11px] text-slate-400 mt-1 px-1"><span>${first}</span><span>${last}</span></div>
        </section>`;
}

function kpiSectionHtml(section) {
    const rows = (section.rows || []).map(row => `
        <li class="flex items-center justify-between gap-3 py-2.5">
            <span class="min-w-0">
                <span class="block text-sm font-semibold text-slate-800 truncate">${escapeHtml(row.primary)}</span>
                <span class="block text-xs text-slate-400 truncate">${escapeHtml(row.secondary)}</span>
            </span>
            <span class="text-sm font-bold text-slate-900 tabular-nums shrink-0">${escapeHtml(row.value)}</span>
        </li>`).join("");
    return `
        <section>
            <h4 class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">${escapeHtml(section.title)}</h4>
            ${rows
                ? `<ul class="divide-y divide-slate-100">${rows}</ul>`
                : `<p class="text-sm text-slate-400 py-2">${escapeHtml(section.empty_text || "No data.")}</p>`}
        </section>`;
}

function renderKpiModal(data) {
    document.getElementById("kpi-modal-title").textContent = data.title || "Details";
    const periodText = data.kpi === "receivables" ? data.as_of_label : data.period_label;
    document.getElementById("kpi-modal-subtitle").textContent =
        [currentActiveCompanyName, periodText].filter(Boolean).join(" · ");

    const headline = data.headline || {};
    let deltaHtml = "";
    if (headline.formatted_delta) {
        const tone = headline.delta_direction === "up" ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700";
        const arrow = headline.delta_direction === "up" ? "↑" : "↓";
        deltaHtml = `<span class="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone}">${arrow} ${escapeHtml(headline.formatted_delta)} ${escapeHtml(headline.prior_label)}</span>`;
    } else if (headline.prior_label) {
        deltaHtml = `<span class="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold bg-slate-100 text-slate-600">${escapeHtml(headline.prior_label)}</span>`;
    }

    const metricTiles = (data.metrics || []).map(m => `
        <div class="rounded-2xl bg-slate-50 p-3">
            <div class="text-[11px] font-bold uppercase tracking-wide text-slate-500">${escapeHtml(m.label)}</div>
            <div class="text-lg font-extrabold text-slate-900 tabular-nums">${escapeHtml(m.value)}</div>
            <div class="text-[11px] text-slate-400 truncate">${escapeHtml(m.hint)}</div>
        </div>`).join("");

    document.getElementById("kpi-modal-body").innerHTML = `
        <p class="text-sm text-slate-600 leading-relaxed">${escapeHtml(data.description)}</p>
        <div class="flex flex-wrap items-center gap-3">
            <span class="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 tabular-nums">${escapeHtml(headline.formatted_value)}</span>
            ${deltaHtml}
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">${metricTiles}</div>
        ${kpiTrendHtml(data.trend)}
        ${(data.sections || []).map(kpiSectionHtml).join("")}`;
}

function inventoryListHtml(title, tone, items, emptyText) {
    const rows = (items || []).map(item => `
        <li class="flex items-center justify-between gap-3 py-2.5">
            <span class="min-w-0">
                <span class="block text-sm font-semibold text-slate-800 truncate">${escapeHtml(item.name)}</span>
                <span class="block text-xs text-slate-400 truncate">${escapeHtml(item.parent_ref || item.category || "")}</span>
            </span>
            <span class="text-right shrink-0">
                <span class="block text-sm font-bold text-slate-900 tabular-nums">${escapeHtml(item.formatted_qty)} ${escapeHtml(item.unit_name)}</span>
                <span class="block text-xs text-slate-500 tabular-nums">${escapeHtml(item.formatted_value)}</span>
            </span>
        </li>`).join("");
    return `
        <section>
            <h4 class="text-xs font-bold uppercase tracking-wider ${tone} mb-1">${escapeHtml(title)}</h4>
            ${rows
                ? `<ul class="divide-y divide-slate-100">${rows}</ul>`
                : `<p class="text-sm text-slate-400 py-2">${escapeHtml(emptyText)}</p>`}
        </section>`;
}

function renderInventoryModal(data) {
    const body = document.getElementById("inventory-modal-body");
    const overview = data.overview || {};
    body.innerHTML = `
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div class="rounded-2xl bg-slate-50 p-3"><div class="text-[11px] font-bold uppercase text-slate-500">Valuation</div><div class="text-lg font-extrabold text-slate-900">${escapeHtml(overview.formatted_valuation)}</div></div>
            <div class="rounded-2xl bg-slate-50 p-3"><div class="text-[11px] font-bold uppercase text-slate-500">Items</div><div class="text-lg font-extrabold text-slate-900">${escapeHtml(overview.total_items)}</div></div>
            <div class="rounded-2xl bg-emerald-50 p-3"><div class="text-[11px] font-bold uppercase text-emerald-700">In stock</div><div class="text-lg font-extrabold text-emerald-800">${escapeHtml(overview.in_stock_count)}</div></div>
            <div class="rounded-2xl bg-rose-50 p-3"><div class="text-[11px] font-bold uppercase text-rose-700">Out of stock</div><div class="text-lg font-extrabold text-rose-800">${escapeHtml(overview.out_of_stock_count)}</div></div>
        </div>
        ${inventoryListHtml("Highest stock", "text-sky-700", data.largest_stock, "No items in stock.")}
        ${inventoryListHtml("Running low", "text-amber-700", data.lowest_stock, "No items running low.")}
        ${inventoryListHtml("Out of stock", "text-rose-700", data.out_of_stock, "All items are in stock.")}`;
}

function trendPillClass(direction) {
    const tone = direction === "up" ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700";
    return `mt-2 sm:mt-4 inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 sm:py-1 text-[11px] sm:text-xs font-semibold leading-tight ${tone}`;
}

function setKpiLoading(isLoading) {
    ["sales", "collections", "receivables", "purchases"].forEach(name => {
        const el = document.getElementById(`kpi-${name}-value`);
        if (el) el.classList.toggle("is-loading", isLoading);
    });
}

// Counts the numeric part of a formatted value (e.g. "₹ 1.84") up from its previous value.
function animateKpiValue(el, formatted) {
    if (!el) return;
    const match = formatted.match(/-?[\d,]+(\.\d+)?/);
    if (!match) {
        el.textContent = formatted;
        return;
    }
    const target = parseFloat(match[0].replace(/,/g, ""));
    const prefix = formatted.slice(0, match.index);
    const suffix = formatted.slice(match.index + match[0].length);
    const decimals = (match[1] || "").length ? match[1].length - 1 : 0;
    const from = parseFloat(el.dataset.value || "0");
    const duration = 700;
    const startTime = performance.now();

    cancelAnimationFrame(el._rafId);
    el.dataset.value = target;

    function frame(now) {
        const t = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        const current = from + (target - from) * eased;
        el.textContent = prefix + current.toLocaleString("en-IN", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }) + suffix;
        if (t < 1) el._rafId = requestAnimationFrame(frame);
    }
    el._rafId = requestAnimationFrame(frame);
}

// Clicking a KPI card pre-fills the chat input with a relevant question.
function handleKpiCardClick(metric) {
    const prompts = {
        sales: "Break down my sales for this period",
        collections: "Break down my collections for this period",
        receivables: "Which customers owe me the most?",
        purchases: "Break down my purchases for this period"
    };
    expandMobileDrawer();
    const input = document.getElementById("chat-input-field");
    if (input) {
        input.value = prompts[metric] || "";
        input.focus();
    }
}

function splitCurrencyAndUnit(formattedString) {
    if (!formattedString) return { value: "₹ 0.00", unit: "" };
    const tokens = formattedString.trim().split(" ");
    if (tokens.length >= 3) {
        // e.g. "₹", "1.84", "Cr"
        return { value: `${tokens[0]} ${tokens[1]}`, unit: tokens[2] };
    }
    return { value: formattedString, unit: "" };
}

// ─── Sync Status ───────────────────────────────────────────────────────────────

async function refreshCompanySyncStatus() {
    const storedAuthToken = localStorage.getItem("o3_token");
    let url = "/api/v1/analytics/sync-status";
    if (currentActiveCompanyId) url += `?company_id=${encodeURIComponent(currentActiveCompanyId)}`;

    try {
        const response = await fetch(url, {
            headers: {
                "Authorization": `Bearer ${storedAuthToken}`,
                "Accept": "application/json"
            }
        });
        if (response.ok) {
            const data = await response.json();
            const labelEl = document.getElementById("books-updated-label");
            if (labelEl) labelEl.textContent = data.books_updated_label || "• Books updated";
        }
    } catch (e) {
        console.warn("Could not retrieve sync status:", e);
    }
}

// ─── Ask O3 Single-Thread Chat ─────────────────────────────────────────────────

async function loadSingleThreadChatHistory() {
    const storedAuthToken = localStorage.getItem("o3_token");
    let url = "/api/v1/agent/messages";
    if (currentActiveCompanyId) url += `?company_id=${encodeURIComponent(currentActiveCompanyId)}`;

    try {
        const response = await fetch(url, {
            headers: {
                "Authorization": `Bearer ${storedAuthToken}`,
                "Accept": "application/json"
            }
        });

        if (response.ok) {
            const data = await response.json();
            const messagesContainer = document.getElementById("chat-messages-container");
            const existingMessages = data.messages || [];

            // If empty, leave initial welcome message
            if (existingMessages.length > 0) {
                // Clear container and append all messages
                messagesContainer.innerHTML = "";
                existingMessages.forEach(msg => {
                    appendMessageBubble(msg.role, msg.content, false);
                });
                scrollChatToBottom();
            }
        }
    } catch (err) {
        console.error("Failed to load chat history:", err);
    }
    refreshSuggestionMode();
}

async function handleSendMessage(event) {
    if (event) event.preventDefault();
    const inputElement = document.getElementById("chat-input-field");
    const userQuery = inputElement.value.trim();
    if (!userQuery) return;

    inputElement.value = "";
    await submitQueryToAssistant(userQuery);
}

function handlePromptChipClick(chipText) {
    // If mobile, ensure drawer is open
    expandMobileDrawer();
    submitQueryToAssistant(chipText);
}

async function submitQueryToAssistant(queryText) {
    const storedAuthToken = localStorage.getItem("o3_token");
    appendMessageBubble("user", queryText, true);
    refreshSuggestionMode();
    skipSuggestionIfAsked(queryText);
    scrollChatToBottom();

    // Show typing dots indicator
    showTypingIndicator();

    try {
        const response = await fetch("/api/v1/agent/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${storedAuthToken}`,
            },
            body: JSON.stringify({
                company_id: currentActiveCompanyId,
                company_name: currentActiveCompanyName,
                message: queryText,
            })
        });

        hideTypingIndicator();

        if (!response.ok) {
            throw new Error(`Chat API error ${response.status}`);
        }

        const data = await response.json();
        appendMessageBubble("assistant", data.content, true);
        scrollChatToBottom();

    } catch (error) {
        hideTypingIndicator();
        appendMessageBubble("assistant", "I encountered an error retrieving data. Please try again.", true);
        scrollChatToBottom();
    }
}

function appendMessageBubble(role, content, animate = false) {
    const container = document.getElementById("chat-messages-container");
    const animClass = animate ? "chat-bubble-animate" : "";

    if (role === "user") {
        const userBubble = document.createElement("div");
        userBubble.className = `flex justify-end ${animClass}`;
        userBubble.dataset.role = "user";
        userBubble.innerHTML = `
            <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-none px-4 py-2.5 max-w-[85%] text-sm leading-relaxed shadow-sm">
                ${escapeHtml(content)}
            </div>
        `;
        container.appendChild(userBubble);
    } else {
        const assistantBubble = document.createElement("div");
        assistantBubble.className = `flex items-start gap-2.5 ${animClass}`;
        assistantBubble.innerHTML = `
            <div class="w-7 h-7 flex items-center justify-center shrink-0 mt-0.5">
                <img src="/static/images/logo.png" alt="O3" class="w-full h-full object-contain">
            </div>
            <div class="chat-prose bg-white border border-slate-200/90 text-slate-800 rounded-2xl rounded-tl-none p-3.5 max-w-[88%] shadow-sm">
                ${formatAssistantContent(content)}
            </div>
        `;
        container.appendChild(assistantBubble);
    }
}

function showTypingIndicator() {
    hideTypingIndicator();
    const container = document.getElementById("chat-messages-container");
    const indicator = document.createElement("div");
    indicator.id = "chat-typing-indicator";
    indicator.className = "flex items-start gap-2.5 chat-bubble-animate";
    indicator.innerHTML = `
        <div class="w-7 h-7 flex items-center justify-center shrink-0 mt-0.5">
            <img src="/static/images/logo.png" alt="O3" class="w-full h-full object-contain">
        </div>
        <div class="bg-white border border-slate-200/90 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm flex items-center gap-1.5">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
        </div>
    `;
    container.appendChild(indicator);
    scrollChatToBottom();
}

function hideTypingIndicator() {
    const existing = document.getElementById("chat-typing-indicator");
    if (existing) existing.remove();
}

function scrollChatToBottom() {
    const container = document.getElementById("chat-messages-container");
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

async function handleClearConversation() {
    if (!confirm("Clear this conversation history?")) return;
    const storedAuthToken = localStorage.getItem("o3_token");
    let url = "/api/v1/agent/messages";
    if (currentActiveCompanyId) url += `?company_id=${encodeURIComponent(currentActiveCompanyId)}`;

    try {
        await fetch(url, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${storedAuthToken}` }
        });

        const container = document.getElementById("chat-messages-container");
        container.innerHTML = `
            <div class="flex items-start gap-2.5">
                <div class="w-7 h-7 flex items-center justify-center shrink-0 mt-0.5">
                    <img src="/static/images/logo.png" alt="O3" class="w-full h-full object-contain">
                </div>
                <div class="chat-prose bg-white border border-slate-200/90 text-slate-800 rounded-2xl rounded-tl-none p-3.5 max-w-[88%] shadow-sm">
                    Hi ${currentAuthenticatedUser ? currentAuthenticatedUser.full_name.split(" ")[0] : "there"}, I'm O3.
                    Ask me about sales, collections, receivables or purchases for <strong>${escapeHtml(currentActiveCompanyName)}</strong>, or tap a question below.
                </div>
            </div>
        `;
        refreshSuggestionMode();
    } catch (e) {
        console.error("Could not clear conversation:", e);
    }
}

// ─── "Try Asking" suggestions ───────────────────────────────────────────────────
// Before the first question all suggestions are shown as chips. Once the chat has started they
// collapse into a single chip whose question changes every SUGGESTION_ROTATE_MS (7s), freeing room for the chat.

const SUGGESTED_QUESTIONS = [
    "How were collections this month?",
    "Which invoices are unpaid?",
    "Who pays me the slowest?",
    "How were sales this week?",
];
const SUGGESTION_ROTATE_MS = 7000;
const SUGGESTION_FADE_MS = 200;
let suggestionIndex = 0;
let suggestionTimer = null;

function conversationHasStarted() {
    const container = document.getElementById("chat-messages-container");
    return !!container && !!container.querySelector('[data-role="user"]');
}

function lastUserQuestion() {
    const bubbles = document.querySelectorAll('#chat-messages-container [data-role="user"]');
    return bubbles.length ? bubbles[bubbles.length - 1].textContent.trim() : "";
}

// Next question in the list, never the one the user asked most recently
function nextSuggestionIndex(from) {
    const lastAsked = lastUserQuestion();
    let next = (from + 1) % SUGGESTED_QUESTIONS.length;
    if (SUGGESTED_QUESTIONS[next] === lastAsked) next = (next + 1) % SUGGESTED_QUESTIONS.length;
    return next;
}

function renderRotatingSuggestion() {
    const chip = document.getElementById("rotating-suggestion");
    if (!chip) return;
    const question = SUGGESTED_QUESTIONS[suggestionIndex];
    chip.textContent = question;
    chip.title = question;
}

function rotateSuggestion(force = false) {
    const chip = document.getElementById("rotating-suggestion");
    if (!chip) return;
    // Don't swap the question under the pointer or while the tab is in the background
    if (!force && (document.hidden || chip.matches(":hover") || chip === document.activeElement)) return;

    suggestionIndex = nextSuggestionIndex(suggestionIndex);
    chip.classList.add("opacity-0");
    setTimeout(() => {
        renderRotatingSuggestion();
        chip.classList.remove("opacity-0");
    }, SUGGESTION_FADE_MS);
}

function startSuggestionRotation() {
    stopSuggestionRotation();
    suggestionTimer = setInterval(() => rotateSuggestion(), SUGGESTION_ROTATE_MS);
}

function stopSuggestionRotation() {
    if (suggestionTimer !== null) {
        clearInterval(suggestionTimer);
        suggestionTimer = null;
    }
}

function refreshSuggestionMode() {
    const full = document.getElementById("suggestions-full");
    const compact = document.getElementById("suggestions-compact");
    if (!full || !compact) return;

    const compactMode = conversationHasStarted();
    full.classList.toggle("hidden", compactMode);
    compact.classList.toggle("hidden", !compactMode);

    if (compactMode) {
        if (suggestionTimer === null) {
            // Start on a question other than the one asked last
            if (SUGGESTED_QUESTIONS[suggestionIndex] === lastUserQuestion()) {
                suggestionIndex = nextSuggestionIndex(suggestionIndex);
            }
            renderRotatingSuggestion();
            startSuggestionRotation();
        }
    } else {
        stopSuggestionRotation();
        suggestionIndex = 0;
    }
}

// Don't keep offering the question that was just asked
function skipSuggestionIfAsked(queryText) {
    if (suggestionTimer !== null && SUGGESTED_QUESTIONS[suggestionIndex] === queryText) {
        rotateSuggestion(true);
        startSuggestionRotation(); // the next question gets a full interval on screen
    }
}

function handleRotatingSuggestionClick() {
    handlePromptChipClick(SUGGESTED_QUESTIONS[suggestionIndex]);
}

// ─── Mobile Drawer Toggle ───────────────────────────────────────────────────────

function setMobileDrawer(expanded) {
    const drawer = document.getElementById("ask-o3-panel");
    const toggleIcon = document.getElementById("mobile-drawer-toggle-icon");
    const backdrop = document.getElementById("drawer-backdrop");
    isMobileDrawerExpanded = expanded;

    drawer.classList.toggle("drawer-collapsed", !expanded);
    // Up arrow while the panel is tucked away, down arrow while it is open.
    if (toggleIcon) toggleIcon.classList.toggle("rotate-180", !expanded);
    if (backdrop) backdrop.classList.toggle("hidden", !expanded);
    if (expanded) scrollChatToBottom();
}

function toggleMobileDrawer() {
    setMobileDrawer(!isMobileDrawerExpanded);
}

function openDrawerAndFocusInput() {
    setMobileDrawer(true);
    const input = document.getElementById("chat-input-field");
    if (input) setTimeout(() => input.focus(), 300);
}

function expandMobileDrawer() {
    setMobileDrawer(true);
}

// ─── Utilities ──────────────────────────────────────────────────────────────────

function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Escapes the reply, then lays it out as paragraphs, bullet rows and blank-line gaps (**bold** kept).
// Interpretation line, supporting facts and clickable "watch" chips under the summary sentence.
function renderSummaryInsights(insights) {
    const wrapper = document.getElementById("executive-insights");
    if (!wrapper) return;

    const interpretation = (insights && insights.interpretation) || "";
    const facts = (insights && insights.facts) || [];
    const watch = (insights && insights.watch) || [];

    document.getElementById("executive-interpretation").textContent = interpretation;
    document.getElementById("executive-interpretation").classList.toggle("hidden", !interpretation);

    document.getElementById("executive-facts").innerHTML = facts.map(fact => `
        <li class="flex gap-2"><span class="mt-2 w-1 h-1 rounded-full bg-indigo-400 shrink-0"></span><span>${escapeHtml(fact)}</span></li>`).join("");

    const watchEl = document.getElementById("executive-watch");
    watchEl.innerHTML = watch.map((item, index) => `
        <button type="button" data-watch-index="${index}"
                class="inline-flex items-center gap-1.5 rounded-full bg-amber-50 text-amber-800 ring-1 ring-amber-200 px-3 py-1 text-xs font-semibold hover:bg-amber-100 transition-colors">
            ${escapeHtml(item.label)} <span aria-hidden="true">→</span>
        </button>`).join("");
    watchEl.querySelectorAll("button").forEach(button => {
        const target = watch[Number(button.dataset.watchIndex)].target;
        button.onclick = () => (target === "inventory" ? openInventoryModal() : openKpiModal(target));
    });

    wrapper.classList.toggle("hidden", !interpretation && !facts.length && !watch.length);
}

// Colours the "up 18%" / "down 9%" parts of the summary sentence (text is escaped first).
function colorizeSummary(text) {
    return escapeHtml(text).replace(/\b(up|down)\s+(\d+%)/gi, (match, direction, pct) => {
        const tone = direction.toLowerCase() === "up" ? "text-emerald-600" : "text-rose-600";
        const arrow = direction.toLowerCase() === "up" ? "↑" : "↓";
        return `<span class="${tone} font-bold whitespace-nowrap">${arrow} ${pct}</span>`;
    });
}

function formatAssistantContent(text) {
    if (!text) return "";
    const bold = line => escapeHtml(line).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    return String(text)
        .split("\n")
        .map(line => {
            const trimmed = line.trim();
            if (!trimmed) return '<div class="chat-gap"></div>';
            const bullet = trimmed.match(/^[•\-*]\s+(.*)$/);
            if (bullet) return `<div class="chat-li"><span>${bold(bullet[1])}</span></div>`;
            return `<p class="chat-p">${bold(trimmed)}</p>`;
        })
        .join("");
}

// ─── Company Switcher ───────────────────────────────────────────────────────────

// Companies the user can switch between.
let availableCompanies = [];

function updateCompanyIdSubtext() {
    const idEl = document.getElementById("profile-menu-company-id");
    const rowEl = document.getElementById("profile-menu-company-id-row");
    if (idEl) idEl.textContent = currentActiveCompanyId || "";
    if (rowEl) rowEl.classList.toggle("hidden", !currentActiveCompanyId);
}

function syncCompanyList() {
    if (!currentActiveCompanyId) return;
    const existing = availableCompanies.find(company => company.id === currentActiveCompanyId);
    if (existing) {
        existing.name = currentActiveCompanyName;
    } else {
        availableCompanies.push({ id: currentActiveCompanyId, name: currentActiveCompanyName });
    }
}

function renderCompanyMenu() {
    const list = document.getElementById("company-menu-list");
    if (!list) return;
    list.innerHTML = "";
    const activeId = currentActiveCompanyId || "current";

    availableCompanies.forEach(company => {
        const isActive = company.id === activeId;
        const item = document.createElement("button");
        item.type = "button";
        item.setAttribute("role", "option");
        item.className = `w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl text-left text-sm font-semibold transition-colors ${
            isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-700 hover:bg-slate-50"}`;
        item.onclick = () => handleCompanySwitch(company.id);

        const textWrapper = document.createElement("div");
        textWrapper.className = "flex flex-col min-w-0";

        const nameEl = document.createElement("span");
        nameEl.className = "truncate font-semibold";
        // Tally appends the books start date, e.g. "(From 1-Apr-2020)"; the menu shows the bare name.
        nameEl.textContent = company.name.replace(/\s*\(\s*From\s[^)]*\)\s*$/i, "");
        textWrapper.appendChild(nameEl);

        const idEl = document.createElement("span");
        idEl.className = "text-[10px] font-mono text-slate-400 truncate";
        idEl.textContent = company.id;
        textWrapper.appendChild(idEl);

        item.appendChild(textWrapper);

        if (isActive) {
            item.insertAdjacentHTML("beforeend",
                '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"></path></svg>');
        }
        list.appendChild(item);
    });
}

function toggleCompanyMenu(event) {
    event.stopPropagation();
    const menu = document.getElementById("company-menu");
    if (!menu.classList.contains("hidden")) {
        closeCompanyMenu();
        return;
    }
    closeProfileMenu();
    syncCompanyList();
    renderCompanyMenu();
    menu.classList.remove("hidden");
    document.getElementById("company-chevron").classList.add("rotate-180");
}

function closeCompanyMenu() {
    const menu = document.getElementById("company-menu");
    if (menu) menu.classList.add("hidden");
    const chevron = document.getElementById("company-chevron");
    if (chevron) chevron.classList.remove("rotate-180");
}

async function handleCompanySwitch(companyId) {
    closeCompanyMenu();
    const activeId = currentActiveCompanyId || "current";
    if (companyId === activeId) return;

    const target = availableCompanies.find(company => company.id === companyId);
    if (!target) return;

    currentActiveCompanyId = companyId;
    currentActiveCompanyName = target.name;
    localStorage.setItem("o3_active_company_id", companyId);

    // Update UI elements immediately
    const compElements = document.querySelectorAll(".company-display-name");
    compElements.forEach(el => el.textContent = target.name);
    const answeringLabel = document.getElementById("answering-company-label");
    if (answeringLabel) answeringLabel.textContent = `Answering for ${target.name}`;
    updateCompanyIdSubtext();

    applySyncPausedState();
    await refreshCompanySyncStatus();
    await loadExecutiveOverviewMetrics(currentSelectedPeriod);
    await loadSingleThreadChatHistory();
}

document.addEventListener("click", event => {
    const menu = document.getElementById("company-menu");
    if (menu && !menu.contains(event.target)) closeCompanyMenu();
});
document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeCompanyMenu();
});

// ─── Profile Menu & Sync Pause ──────────────────────────────────────────────────

function toggleProfileMenu(event) {
    event.stopPropagation();
    closeCompanyMenu();
    const menu = document.getElementById("profile-menu");
    if (!menu.classList.contains("hidden")) {
        closeProfileMenu();
        return;
    }

    if (currentAuthenticatedUser) {
        document.getElementById("profile-menu-name").textContent = currentAuthenticatedUser.full_name || "Account";
        document.getElementById("profile-menu-email").textContent = currentAuthenticatedUser.email || "";
    }

    // Open beside the avatar on desktop (it sits at the bottom of the rail), below it on mobile.
    const rect = event.currentTarget.getBoundingClientRect();
    if (window.innerWidth >= 768) {
        menu.style.left = `${rect.right + 12}px`;
        menu.style.bottom = `${window.innerHeight - rect.bottom}px`;
        menu.style.top = "auto";
        menu.style.right = "auto";
    } else {
        menu.style.right = "16px";
        menu.style.top = `${rect.bottom + 8}px`;
        menu.style.left = "auto";
        menu.style.bottom = "auto";
    }
    menu.classList.remove("hidden");
}

function closeProfileMenu() {
    const menu = document.getElementById("profile-menu");
    if (menu) menu.classList.add("hidden");
}

document.addEventListener("click", event => {
    const menu = document.getElementById("profile-menu");
    if (menu && !menu.contains(event.target)) closeProfileMenu();
});
document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeProfileMenu();
});

function syncPauseStorageKey() {
    return `o3_sync_paused_${currentActiveCompanyId || "default"}`;
}

function formatPauseTimestamp(isoString) {
    return new Date(isoString).toLocaleString("en-IN", {
        day: "numeric", month: "short", year: "numeric",
        hour: "numeric", minute: "2-digit", hour12: true
    });
}

// Shows or hides the "sync was paused on" label and updates the menu button to match.
function applySyncPausedState() {
    const pausedAt = localStorage.getItem(syncPauseStorageKey());
    const label = document.getElementById("sync-paused-label");
    const text = document.getElementById("sync-paused-text");
    const menuLabel = document.getElementById("pause-sync-label");
    const menuIcon = document.getElementById("pause-sync-icon");

    if (pausedAt) {
        text.textContent = `The sync was paused on ${formatPauseTimestamp(pausedAt)}`;
        label.classList.remove("hidden");
        menuLabel.textContent = "Resume Sync";
        menuIcon.innerHTML = '<path d="M6 4l10 6-10 6V4z"></path>';
    } else {
        label.classList.add("hidden");
        menuLabel.textContent = "Pause Sync";
        menuIcon.innerHTML = '<path d="M6 4h3v12H6V4zm5 0h3v12h-3V4z"></path>';
    }
}

function handleToggleSync() {
    if (localStorage.getItem(syncPauseStorageKey())) {
        localStorage.removeItem(syncPauseStorageKey());
    } else {
        localStorage.setItem(syncPauseStorageKey(), new Date().toISOString());
    }
    applySyncPausedState();
    closeProfileMenu();
}

function handleUserLogout() {
    localStorage.removeItem("o3_token");
    localStorage.removeItem("o3_user");
    window.location.href = "/login";
}

// Bootstrap on window load
document.addEventListener("DOMContentLoaded", initializeDashboardApplication);
