/**
 * AI BI Dashboard – Frontend Logic (Vanilla JS)
 * Handles theme, KPI rendering, ECharts, DataTables, filters
 */

// -------------------------------------------------
// Theme
// -------------------------------------------------
function initTheme() {
    const saved = localStorage.getItem("bi_theme") || "light";
    document.documentElement.setAttribute("data-theme", saved);
    updateThemeIcon(saved);

    const btn = document.getElementById("themeToggle");
    if (btn) {
        btn.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("bi_theme", next);
            updateThemeIcon(next);
            // Dark/Light pe charts dubara banao taaki axis text sahi color le
            if (window._lastChartsData) {
                renderCharts(window._lastChartsData);
            } else if (window._chartInstances) {
                Object.values(window._chartInstances).forEach(c => c.resize());
            }
        });
    }
}

function updateThemeIcon(theme) {
    const btn = document.getElementById("themeToggle");
    if (!btn) return;
    btn.innerHTML = theme === "dark"
        ? '<i class="fas fa-sun"></i>'
        : '<i class="fas fa-moon"></i>';
}

// -------------------------------------------------
// Formatting helpers
// -------------------------------------------------
function formatValue(val, fmt) {
    if (val == null || isNaN(val)) return "—";
    const n = Number(val);
    if (fmt === "currency") {
        if (Math.abs(n) >= 1e7) return "₹" + (n / 1e7).toFixed(2) + " Cr";
        if (Math.abs(n) >= 1e5) return "₹" + (n / 1e5).toFixed(2) + " L";
        return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
    }
    if (fmt === "percent") return n.toFixed(1) + "%";
    return n.toLocaleString("en-IN");
}

/** Compact axis formatter – short labels so they never clip to 0.00 */
function axisCurrency(val) {
    const n = Number(val);
    if (isNaN(n) || n === 0) return "0";
    const abs = Math.abs(n);
    if (abs >= 1e7) {
        const cr = n / 1e7;
        return (Math.abs(cr) >= 100 ? cr.toFixed(0) : cr.toFixed(1)) + " Cr";
    }
    if (abs >= 1e5) return (n / 1e5).toFixed(1) + " L";
    if (abs >= 1e3) return (n / 1e3).toFixed(0) + " K";
    return n.toFixed(0);
}

const colorMap = {
    primary: "bg-primary-soft",
    success: "bg-success-soft",
    warning: "bg-warning-soft",
    info: "bg-info-soft",
    danger: "bg-danger-soft",
    secondary: "bg-secondary-soft"
};

// -------------------------------------------------
// KPI Cards
// -------------------------------------------------
function renderKPIs(kpis) {
    const row = document.getElementById("kpiRow");
    if (!row) return;
    row.innerHTML = "";
    kpis.forEach(kpi => {
        const col = document.createElement("div");
        col.className = "col-6 col-md-4 col-lg-2";
        col.innerHTML = `
      <div class="card kpi-card h-100">
        <div class="card-body d-flex align-items-center gap-3 py-3">
          <div class="kpi-icon ${colorMap[kpi.color] || "bg-primary-soft"}">
            <i class="fas ${kpi.icon}"></i>
          </div>
          <div>
            <div class="kpi-title">${kpi.title}</div>
            <div class="kpi-value">${formatValue(kpi.value, kpi.format)}</div>
          </div>
        </div>
      </div>`;
        row.appendChild(col);
    });
}

// -------------------------------------------------
// ECharts Rendering
// -------------------------------------------------
window._chartInstances = {};

function isDark() {
    return document.documentElement.getAttribute("data-theme") === "dark";
}

function baseTextStyle() {
    return {
        color: isDark() ? "#f1f5f9" : "#1f2937",
        fontSize: 11
    };
}

function renderCharts(charts) {
    const row = document.getElementById("chartsRow");
    if (!row) return;

    // Theme toggle ke liye save
    window._lastChartsData = charts;

    Object.values(window._chartInstances).forEach(c => c.dispose());
    window._chartInstances = {};
    row.innerHTML = "";

    const chartDefs = [
        { key: "monthly_trend", span: 6 },
        { key: "region_bar", span: 6 },
        { key: "category_pie", span: 4 },
        { key: "category_donut", span: 4 },
        { key: "top_customers", span: 4 },
        { key: "bottom_customers", span: 4 },
        { key: "treemap", span: 4 },
        { key: "heatmap", span: 8 },
        { key: "growth_bar", span: 4 }
    ];

    chartDefs.forEach(def => {
        const cfg = charts[def.key];
        if (!cfg) return;

        const col = document.createElement("div");
        col.className = `col-12 col-lg-${def.span}`;
        const id = `chart_${def.key}`;
        col.innerHTML = `
      <div class="card chart-card border-0 shadow-sm">
        <div class="card-header bg-transparent border-0 fw-semibold small py-2">
          ${cfg.title}
        </div>
        <div class="card-body">
          <div id="${id}" class="chart-container"></div>
        </div>
      </div>`;
        row.appendChild(col);

        setTimeout(() => createChart(id, cfg), 50);
    });
}

function createChart(domId, cfg) {
    const el = document.getElementById(domId);
    if (!el) return;
    const chart = echarts.init(el, null, { renderer: "canvas" });
    window._chartInstances[domId] = chart;

    // Dark mode ke liye bright text colors
    const labelColor = isDark() ? "#f1f5f9" : "#1f2937";
    const lineColor = isDark() ? "#64748b" : "#94a3b8";
    const splitColor = isDark() ? "#334155" : "#e5e7eb";

    let option = {};

    if (cfg.type === "line") {
        option = {
            tooltip: {
                trigger: "axis",
                valueFormatter: v => formatValue(v, "currency")
            },
            legend: { textStyle: { color: labelColor }, top: 0 },
            grid: { left: 65, right: 20, top: 40, bottom: 40 },
            xAxis: {
                type: "category",
                data: cfg.labels,
                axisLabel: { color: labelColor, fontSize: 12, show: true },
                axisLine: { show: true, lineStyle: { color: lineColor } },
                axisTick: { show: true, lineStyle: { color: lineColor } }
            },
            yAxis: {
                type: "value",
                axisLabel: {
                    color: labelColor,
                    fontSize: 11,
                    show: true,
                    formatter: axisCurrency
                },
                axisLine: { show: true, lineStyle: { color: lineColor } },
                splitLine: { show: true, lineStyle: { color: splitColor } }
            },
            series: cfg.datasets.map(ds => ({
                name: ds.name,
                type: "line",
                smooth: true,
                data: ds.data,
                areaStyle: { opacity: 0.15 },
                itemStyle: { color: "#3b82f6" },
                lineStyle: { width: 3 },
                label: { show: false }
            }))
        };
    } else if (cfg.type === "bar") {
        option = {
            tooltip: {
                trigger: "axis",
                valueFormatter: v => formatValue(v, "currency")
            },
            grid: { left: 65, right: 16, top: 24, bottom: 90 },
            xAxis: {
                type: "category",
                data: cfg.labels,
                axisLabel: {
                    color: labelColor,
                    rotate: 35,
                    fontSize: 10,
                    interval: 0,
                    hideOverlap: true,
                    show: true
                },
                axisLine: { show: true, lineStyle: { color: lineColor } },
                axisTick: { show: false }
            },
            yAxis: {
                type: "value",
                axisLabel: {
                    color: labelColor,
                    fontSize: 11,
                    show: true,
                    formatter: axisCurrency
                },
                axisLine: { show: true, lineStyle: { color: lineColor } },
                splitLine: { show: true, lineStyle: { color: splitColor } }
            },
            series: cfg.datasets.map(ds => ({
                name: ds.name,
                type: "bar",
                data: ds.data,
                barMaxWidth: 36,
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: "#3b82f6" },
                        { offset: 1, color: "#1d4ed8" }
                    ]),
                    borderRadius: [4, 4, 0, 0]
                },
                label: { show: false }
            }))
        };
    } else if (cfg.type === "pie" || cfg.type === "donut") {
        option = {
            tooltip: {
                trigger: "item",
                formatter: (p) => {
                    const val = formatValue(p.value, "currency");
                    return `${p.name}<br/>${val} (${p.percent}%)`;
                }
            },
            legend: {
                type: "scroll",
                orient: "vertical",
                right: 4,
                top: "middle",
                height: "80%",
                textStyle: { color: labelColor, fontSize: 11 },
                pageTextStyle: { color: labelColor },
                formatter: (name) => {
                    return name.length > 18 ? name.slice(0, 16) + "…" : name;
                }
            },
            series: [{
                type: "pie",
                radius: cfg.type === "donut" ? ["42%", "68%"] : ["0%", "65%"],
                center: ["36%", "50%"],
                data: cfg.labels.map((l, i) => ({ name: l, value: cfg.data[i] })),
                label: { show: false },
                labelLine: { show: false },
                avoidLabelOverlap: true,
                emphasis: {
                    itemStyle: { shadowBlur: 12, shadowColor: "rgba(0,0,0,.25)" },
                    label: { show: false }
                }
            }]
        };
    } else if (cfg.type === "treemap") {
        option = {
            tooltip: { formatter: p => `${p.name}: ${formatValue(p.value, "currency")}` },
            series: [{
                type: "treemap",
                data: cfg.data,
                roam: false,
                nodeClick: false,
                breadcrumb: { show: false },
                label: {
                    show: true,
                    formatter: (p) => {
                        const name = p.name || "";
                        const val = axisCurrency(p.value);
                        if (name.length <= 14) return name + "\n" + val;
                        return name.slice(0, 12) + "…\n" + val;
                    },
                    fontSize: 11,
                    color: "#fff",
                    textShadowColor: "rgba(0,0,0,.4)",
                    textShadowBlur: 2
                },
                upperLabel: { show: false },
                levels: [{
                    itemStyle: {
                        borderColor: isDark() ? "#1e293b" : "#fff",
                        borderWidth: 2,
                        gapWidth: 3
                    },
                    label: { fontSize: 12, fontWeight: "600" }
                }]
            }]
        };
    } else if (cfg.type === "heatmap") {
        const flat = [];
        cfg.data.forEach((row, yi) => {
            row.forEach((val, xi) => flat.push([xi, yi, val]));
        });
        const maxVal = Math.max(...flat.map(d => d[2]), 1);
        option = {
            tooltip: {
                formatter: p => `${cfg.y_labels[p.value[1]]} – ${cfg.x_labels[p.value[0]]}: ${formatValue(p.value[2], "currency")}`
            },
            grid: { left: 110, right: 24, top: 16, bottom: 72 },
            xAxis: {
                type: "category",
                data: cfg.x_labels,
                axisLabel: {
                    color: labelColor,
                    fontSize: 12,
                    margin: 10,
                    show: true
                },
                splitArea: { show: true },
                axisTick: { show: false },
                axisLine: { lineStyle: { color: lineColor } }
            },
            yAxis: {
                type: "category",
                data: cfg.y_labels,
                axisLabel: {
                    color: labelColor,
                    fontSize: 10,
                    show: true
                },
                splitArea: { show: true },
                axisLine: { lineStyle: { color: lineColor } }
            },
            visualMap: {
                min: 0,
                max: maxVal,
                calculable: true,
                orient: "horizontal",
                left: "center",
                bottom: 4,
                itemWidth: 14,
                itemHeight: 120,
                inRange: { color: ["#dbeafe", "#3b82f6", "#1e3a8a"] },
                textStyle: { color: labelColor, fontSize: 10 },
                formatter: (v) => axisCurrency(v)
            },
            series: [{
                type: "heatmap",
                data: flat,
                label: { show: false },
                emphasis: { itemStyle: { shadowBlur: 10 } }
            }]
        };
    }

    chart.setOption(option);
    window.addEventListener("resize", () => chart.resize());
}

// -------------------------------------------------
// Insights & Recommendations
// -------------------------------------------------
function renderInsights(insights, recommendations) {
    const iList = document.getElementById("insightsList");
    const rList = document.getElementById("recommendationsList");
    if (!iList || !rList) return;

    iList.innerHTML = insights.map(ins => `
    <div class="insight-item">
      <h6><i class="fas fa-check-circle text-success me-1"></i>${ins.title}</h6>
      <p>${ins.text}</p>
    </div>`).join("") || "<p class='text-muted small'>No insights available.</p>";

    rList.innerHTML = recommendations.map(rec => `
    <div class="rec-item priority-${rec.priority}">
      <h6>
        <span class="badge bg-${rec.priority === "high" ? "danger" : rec.priority === "medium" ? "warning text-dark" : "success"} me-1">
          ${rec.priority.toUpperCase()}
        </span>
        Recommendation
      </h6>
      <p>${rec.text}</p>
    </div>`).join("") || "<p class='text-muted small'>No recommendations.</p>";
}

// -------------------------------------------------
// Data Table
// -------------------------------------------------
let dataTableInstance = null;

function renderTable(table) {
    if (!table || !table.columns) return;

    if (dataTableInstance) {
        dataTableInstance.destroy();
        dataTableInstance = null;
    }

    const thead = document.querySelector("#dataTable thead");
    const tbody = document.querySelector("#dataTable tbody");
    thead.innerHTML = "<tr>" + table.columns.map(c => `<th>${c}</th>`).join("") + "</tr>";
    tbody.innerHTML = "";

    dataTableInstance = $("#dataTable").DataTable({
        data: table.data,
        columns: table.columns.map(c => ({ title: c })),
        pageLength: 15,
        lengthMenu: [10, 15, 25, 50, 100],
        order: [],
        scrollX: true,
        language: {
            search: "",
            searchPlaceholder: "Filter rows…"
        },
        dom: '<"row"<"col-sm-6"l><"col-sm-6"f>>rtip'
    });

    const searchBox = document.getElementById("tableSearch");
    if (searchBox) {
        searchBox.oninput = () => dataTableInstance.search(searchBox.value).draw();
    }
}

// -------------------------------------------------
// Filters
// -------------------------------------------------
function setupFilters(roles, options) {
    const row = document.getElementById("filterRow");
    if (!row) return;

    row.querySelectorAll(".filter-select-wrap").forEach(el => el.remove());

    const interesting = ["category", "state", "region", "product"];
    const colsToShow = [];
    interesting.forEach(role => {
        if (roles[role] && roles[role].length) {
            colsToShow.push(roles[role][0]);
        }
    });

    colsToShow.forEach(col => {
        const vals = (options && options[col]) || [];
        if (!vals.length) return;
        const wrap = document.createElement("div");
        wrap.className = "col-auto filter-select-wrap";
        wrap.innerHTML = `
      <select class="form-select form-select-sm filter-select" data-col="${col}" style="min-width:140px">
        <option value="">All ${col}</option>
        ${vals.map(v => `<option value="${v}">${v}</option>`).join("")}
      </select>`;
        row.insertBefore(wrap, row.lastElementChild);
    });

    document.querySelectorAll(".filter-select").forEach(sel => {
        sel.addEventListener("change", applyFilters);
    });

    const resetBtn = document.getElementById("resetFilters");
    if (resetBtn) {
        resetBtn.onclick = () => {
            document.querySelectorAll(".filter-select").forEach(s => s.value = "");
            applyFilters();
        };
    }
}

async function applyFilters() {
    const filters = {};
    document.querySelectorAll(".filter-select").forEach(sel => {
        if (sel.value) filters[sel.dataset.col] = [sel.value];
    });

    try {
        const res = await fetch("/api/filter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filters })
        });
        const data = await res.json();
        if (data.error) return;

        renderKPIs(data.kpis);
        renderCharts(data.charts);
        renderTable(data.table);
        document.getElementById("rowBadge").textContent = data.rows + " rows";
    } catch (e) {
        console.error("Filter error", e);
    }
}

// -------------------------------------------------
// Main Dashboard Loader
// -------------------------------------------------
async function loadDashboard() {
    let data = null;
    const cached = sessionStorage.getItem("bi_data");
    if (cached) {
        try { data = JSON.parse(cached); } catch (e) { }
    }

    if (!data || !data.kpis) {
        try {
            const res = await fetch("/api/data");
            data = await res.json();
            if (data.error) {
                window.location.href = "/";
                return;
            }
        } catch (e) {
            window.location.href = "/";
            return;
        }
    }

    const fileBadge = document.getElementById("fileBadge");
    const rowBadge = document.getElementById("rowBadge");
    if (fileBadge) fileBadge.textContent = data.filename || "Data";
    if (rowBadge) rowBadge.textContent = (data.rows || 0) + " rows";

    renderKPIs(data.kpis || []);
    renderCharts(data.charts || {});
    renderInsights(data.insights || [], data.recommendations || []);
    renderTable(data.table || {});

    try {
        const optRes = await fetch("/api/filter_options");
        const options = await optRes.json();
        setupFilters(data.roles || {}, options);
    } catch (e) {
        setupFilters(data.roles || {}, {});
    }

    const pdfBtn = document.getElementById("exportPdfBtn");
    if (pdfBtn) {
        pdfBtn.onclick = (e) => {
            e.preventDefault();
            window.print();
        };
    }
}