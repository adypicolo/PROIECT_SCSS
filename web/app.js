const state = {
  dataset: null,
  result: null,
  activeView: "main",
};
const SIDEBAR_STORAGE_KEY = "lv-sidebar-collapsed";
const ACTIVE_VIEW_STORAGE_KEY = "lv-active-view";

const isFileProtocol = window.location.protocol === "file:";
const apiBase = (() => {
  if (isFileProtocol) return null;
  return `${window.location.origin}/api`;
})();

const elements = {
  crmContainer: document.querySelector(".crm-container"),
  sidebarToggle: document.querySelector("#sidebarToggle"),
  viewButtons: Array.from(document.querySelectorAll("[data-view-trigger]")),
  viewPanels: Array.from(document.querySelectorAll("[data-view-panel]")),
  titleInput: document.querySelector("#titleInput"),
  scenarioInput: document.querySelector("#scenarioInput"),
  notesInput: document.querySelector("#notesInput"),
  rowsInput: document.querySelector("#rowsInput"),
  colsInput: document.querySelector("#colsInput"),
  matrixMeta: document.querySelector("#matrixMeta"),
  matrixEditor: document.querySelector("#matrixEditor"),
  statusBanner: document.querySelector("#statusBanner"),
  statusMessage: document.querySelector("#statusMessage"),
  summaryCards: document.querySelector("#summaryCards"),
  chartsGrid: document.querySelector("#chartsGrid"),
  interpretationPanel: document.querySelector("#interpretationPanel"),
  iterationsList: document.querySelector("#iterationsList"),
  fileInput: document.querySelector("#fileInput"),
  sampleBtn: document.querySelector("#sampleBtn"),
  buildBtn: document.querySelector("#buildBtn"),
  solveBtn: document.querySelector("#solveBtn"),
  exportJsonBtn: document.querySelector("#exportJsonBtn"),
  exportPdfBtn: document.querySelector("#exportPdfBtn"),
};
const SVG_NS = "http://www.w3.org/2000/svg";
let chartVisibilityObserver = null;
let statusHideTimer = null;
let exportStylesText = null;

const numberFormat = new Intl.NumberFormat("ro-RO", {
  maximumFractionDigits: 2,
});

function makeDefaultDataset(rows, cols) {
  return {
    title: "",
    scenario: "",
    notes: "",
    source_labels: Array.from({ length: rows }, (_, index) => `A${index + 1}`),
    destination_labels: Array.from({ length: cols }, (_, index) => `B${index + 1}`),
    cost_matrix: Array.from({ length: rows }, () => Array.from({ length: cols }, () => 0)),
    supply: Array.from({ length: rows }, () => 0),
    demand: Array.from({ length: cols }, () => 0),
  };
}

function clearStatusTimer() {
  if (statusHideTimer) {
    window.clearTimeout(statusHideTimer);
    statusHideTimer = null;
  }
}

function setStatus(message, options = {}) {
  const { autoHideMs = null } = options;
  clearStatusTimer();
  elements.statusMessage.textContent = message;
  elements.statusBanner.classList.remove("is-hidden");
  if (autoHideMs) {
    statusHideTimer = window.setTimeout(() => {
      hideStatus();
    }, autoHideMs);
  }
}

function hideStatus() {
  clearStatusTimer();
  elements.statusBanner.classList.add("is-hidden");
}

function readStoredSidebarState() {
  try {
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1";
  } catch (_error) {
    return false;
  }
}

function readStoredActiveView() {
  try {
    const storedView = window.localStorage.getItem(ACTIVE_VIEW_STORAGE_KEY);
    return storedView || "main";
  } catch (_error) {
    return "main";
  }
}

function updateSidebarToggle(collapsed) {
  const label = collapsed ? "Afișează bara laterală" : "Retrage bara laterală";
  elements.sidebarToggle.textContent = collapsed ? ">" : "<";
  elements.sidebarToggle.setAttribute("aria-label", label);
  elements.sidebarToggle.setAttribute("title", label);
  elements.sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
}

function setSidebarCollapsed(collapsed) {
  elements.crmContainer.classList.toggle("sidebar-collapsed", collapsed);
  updateSidebarToggle(collapsed);
  try {
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? "1" : "0");
  } catch (_error) {
  }
}

function toggleSidebar() {
  const isCollapsed = elements.crmContainer.classList.contains("sidebar-collapsed");
  setSidebarCollapsed(!isCollapsed);
}

function syncSidebarForViewport() {
  if (window.innerWidth <= 860) {
    elements.crmContainer.classList.remove("sidebar-collapsed");
    updateSidebarToggle(false);
    return;
  }
  setSidebarCollapsed(readStoredSidebarState());
}

function setActiveView(view) {
  const availableViews = new Set(elements.viewButtons.map((button) => button.dataset.viewTrigger));
  const nextView = availableViews.has(view) ? view : "main";
  state.activeView = nextView;

  elements.viewButtons.forEach((button) => {
    const isActive = button.dataset.viewTrigger === nextView;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });

  elements.viewPanels.forEach((panel) => {
    panel.classList.toggle("is-hidden", panel.dataset.viewPanel !== nextView);
  });

  try {
    window.localStorage.setItem(ACTIVE_VIEW_STORAGE_KEY, nextView);
  } catch (_error) {
  }
}

function formatNumber(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return numberFormat.format(value);
}

function syncDatasetMeta() {
  if (!state.dataset) return;
  state.dataset.title = elements.titleInput.value.trim();
  state.dataset.scenario = elements.scenarioInput.value.trim();
  state.dataset.notes = elements.notesInput.value.trim();
}

function applyDataset(dataset) {
  state.dataset = cloneData(dataset);
  state.result = null;

  elements.titleInput.value = state.dataset.title || "";
  elements.scenarioInput.value = state.dataset.scenario || "";
  elements.notesInput.value = state.dataset.notes || "";
  elements.rowsInput.value = String(state.dataset.supply.length);
  elements.colsInput.value = String(state.dataset.demand.length);

  renderMatrixEditor();
  renderSummary(null);
  renderCharts(null, null);
  renderInterpretation(null);
  renderIterations(null);
}

function cloneData(value) {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

function renderMatrixEditor() {
  const dataset = state.dataset;
  if (!dataset) return;

  const rows = dataset.supply.length;
  const cols = dataset.demand.length;

  const wrap = document.createElement("div");
  wrap.className = "matrix-table-wrap";

  const table = document.createElement("table");
  table.className = "matrix-table";

  const headerRow = document.createElement("tr");
  headerRow.appendChild(document.createElement("th"));

  dataset.destination_labels.forEach((label, colIndex) => {
    const cell = document.createElement("th");
    const input = document.createElement("input");
    input.type = "text";
    input.value = label || `B${colIndex + 1}`;
    input.addEventListener("input", () => {
      dataset.destination_labels[colIndex] = input.value.trim() || `B${colIndex + 1}`;
    });
    const wrapper = document.createElement("label");
    wrapper.className = "cell-input";
    wrapper.appendChild(input);
    cell.appendChild(wrapper);
    headerRow.appendChild(cell);
  });

  const supplyHeader = document.createElement("th");
  supplyHeader.textContent = "Disponibil";
  headerRow.appendChild(supplyHeader);
  table.appendChild(headerRow);

  for (let rowIndex = 0; rowIndex < rows; rowIndex += 1) {
    const row = document.createElement("tr");

    const labelCell = document.createElement("th");
    labelCell.className = "matrix-label";
    const labelInput = document.createElement("input");
    labelInput.type = "text";
    labelInput.value = dataset.source_labels[rowIndex] || `A${rowIndex + 1}`;
    labelInput.addEventListener("input", () => {
      dataset.source_labels[rowIndex] = labelInput.value.trim() || `A${rowIndex + 1}`;
    });
    labelCell.appendChild(labelInput);
    row.appendChild(labelCell);

    for (let colIndex = 0; colIndex < cols; colIndex += 1) {
      const cell = document.createElement("td");
      const input = document.createElement("input");
      input.type = "text";
      input.inputMode = "decimal";
      input.value = dataset.cost_matrix[rowIndex][colIndex];
      input.addEventListener("input", () => {
        dataset.cost_matrix[rowIndex][colIndex] = input.value;
      });
      const wrapper = document.createElement("label");
      wrapper.className = "cell-input";
      wrapper.appendChild(input);
      cell.appendChild(wrapper);
      row.appendChild(cell);
    }

    const supplyCell = document.createElement("td");
    const supplyInput = document.createElement("input");
    supplyInput.type = "text";
    supplyInput.inputMode = "decimal";
    supplyInput.value = dataset.supply[rowIndex];
    supplyInput.addEventListener("input", () => {
      dataset.supply[rowIndex] = supplyInput.value;
    });
    const supplyWrap = document.createElement("label");
    supplyWrap.className = "cell-input";
    supplyWrap.appendChild(supplyInput);
    supplyCell.appendChild(supplyWrap);
    row.appendChild(supplyCell);

    table.appendChild(row);
  }

  const demandRow = document.createElement("tr");
  const demandLabel = document.createElement("th");
  demandLabel.textContent = "Necesar";
  demandRow.appendChild(demandLabel);

  for (let colIndex = 0; colIndex < cols; colIndex += 1) {
    const cell = document.createElement("td");
    const input = document.createElement("input");
    input.type = "text";
    input.inputMode = "decimal";
    input.value = dataset.demand[colIndex];
    input.addEventListener("input", () => {
      dataset.demand[colIndex] = input.value;
    });

    const wrapper = document.createElement("label");
    wrapper.className = "cell-input";
    wrapper.appendChild(input);
    cell.appendChild(wrapper);
    demandRow.appendChild(cell);
  }

  const placeholder = document.createElement("td");
  placeholder.innerHTML = "<strong>&Sigma;</strong>";
  placeholder.style.textAlign = "center";
  placeholder.style.color = "var(--text-muted)";
  demandRow.appendChild(placeholder);
  table.appendChild(demandRow);

  wrap.appendChild(table);
  elements.matrixEditor.replaceChildren(wrap);
  elements.matrixMeta.textContent = `${rows} surse x ${cols} destinatii. Poti edita direct costurile, etichetele si capacitatile.`;
}

function toNumber(value) {
  if (typeof value === "number") return value;
  const text = String(value).trim().replaceAll(" ", "").replace(",", ".");
  if (!text) {
    throw new Error("Toate campurile numerice trebuie completate.");
  }
  const parsed = Number(text);
  if (Number.isNaN(parsed)) {
    throw new Error(`Valoare numerica invalida: ${value}`);
  }
  return parsed;
}

function collectDataset() {
  if (!state.dataset) {
    throw new Error("Nu exista matrice activa.");
  }

  syncDatasetMeta();
  const rows = state.dataset.supply.length;
  const cols = state.dataset.demand.length;

  const costMatrix = state.dataset.cost_matrix.map((row) => row.map((value) => toNumber(value)));
  const supply = state.dataset.supply.map((value) => toNumber(value));
  const demand = state.dataset.demand.map((value) => toNumber(value));
  const sourceLabels = state.dataset.source_labels.map((value, index) => value.trim() || `A${index + 1}`);
  const destinationLabels = state.dataset.destination_labels.map((value, index) => value.trim() || `B${index + 1}`);

  if (costMatrix.length !== rows || costMatrix.some((row) => row.length !== cols)) {
    throw new Error("Matricea de costuri este incompleta.");
  }

  return {
    title: state.dataset.title,
    scenario: state.dataset.scenario,
    notes: state.dataset.notes,
    source_labels: sourceLabels,
    destination_labels: destinationLabels,
    cost_matrix: costMatrix,
    supply,
    demand,
  };
}

async function requestJson(url, payload) {
  if (!apiBase) {
    throw new Error("Pagina a fost deschisa direct din fisier. Porneste webapp.py si acceseaza site-ul prin http://127.0.0.1:8000.");
  }
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "Cererea a esuat.");
  }
  return data;
}

async function requestBlob(url, payload) {
  if (!apiBase) {
    throw new Error("Pagina a fost deschisa direct din fisier. Porneste webapp.py si acceseaza site-ul prin http://127.0.0.1:8000.");
  }
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMessage = "Exportul a esuat.";
    try {
      const data = await response.json();
      errorMessage = data.error || errorMessage;
    } catch (_error) {
    }
    throw new Error(errorMessage);
  }

  return {
    blob: await response.blob(),
    filename:
      response.headers
        .get("Content-Disposition")
        ?.match(/filename="(.+)"/)?.[1] || "download.bin",
  };
}

function waitForNextFrame() {
  return new Promise((resolve) => {
    requestAnimationFrame(resolve);
  });
}

function escapeMarkup(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function collectExportStylesText() {
  if (exportStylesText) return exportStylesText;

  const chunks = [];
  Array.from(document.styleSheets).forEach((sheet) => {
    try {
      const rules = Array.from(sheet.cssRules || []);
      if (!rules.length) return;
      chunks.push(rules.map((rule) => rule.cssText).join("\n"));
    } catch (_error) {
    }
  });

  chunks.push(`
    * {
      animation: none !important;
      transition: none !important;
      caret-color: transparent !important;
    }
    html, body {
      margin: 0 !important;
      padding: 0 !important;
      background: transparent !important;
    }
    .pdf-export-root {
      margin: 0;
      padding: 0;
      background: transparent;
    }
    .chart-card,
    .info-card {
      opacity: 1 !important;
      transform: none !important;
    }
    .chart-area-path {
      opacity: 1 !important;
      transform: none !important;
    }
    .chart-line-path,
    .network-line {
      stroke-dashoffset: 0 !important;
    }
    .chart-point-group,
    .network-node-group,
    .coverage-row {
      opacity: 1 !important;
      transform: none !important;
    }
    .coverage-need-bar,
    .coverage-fill {
      width: var(--target-width) !important;
    }
  `);

  exportStylesText = chunks.join("\n").replace(/url\([^)]+\)/g, "none").replace(/@import[^;]+;/g, "");
  return exportStylesText;
}

async function captureElementAsPngDataUrl(element, width = 1100) {
  const sandbox = document.createElement("div");
  sandbox.style.position = "fixed";
  sandbox.style.left = "-20000px";
  sandbox.style.top = "0";
  sandbox.style.width = `${Math.round(width)}px`;
  sandbox.style.padding = "0";
  sandbox.style.opacity = "0";
  sandbox.style.pointerEvents = "none";
  sandbox.style.zIndex = "-1";

  const clone = element.cloneNode(true);
  clone.classList.add("is-visible");
  clone.style.margin = "0";

  sandbox.appendChild(clone);
  document.body.appendChild(sandbox);

  try {
    await waitForNextFrame();
    await waitForNextFrame();

    const rect = clone.getBoundingClientRect();
    const renderWidth = Math.max(1, Math.ceil(rect.width));
    const renderHeight = Math.max(1, Math.ceil(rect.height));
    const stylesText = collectExportStylesText();
    const xhtml = `
      <div xmlns="http://www.w3.org/1999/xhtml" class="pdf-export-root">
        ${clone.outerHTML}
      </div>
    `;
    const svgMarkup = `
      <svg xmlns="http://www.w3.org/2000/svg" width="${renderWidth}" height="${renderHeight}" viewBox="0 0 ${renderWidth} ${renderHeight}">
        <foreignObject width="100%" height="100%">
          <style>${escapeMarkup(stylesText)}</style>
          ${xhtml}
        </foreignObject>
      </svg>
    `;

    const svgBlob = new Blob([svgMarkup], { type: "image/svg+xml;charset=utf-8" });
    const blobUrl = URL.createObjectURL(svgBlob);

    try {
      const image = await new Promise((resolve, reject) => {
        const nextImage = new Image();
        nextImage.decoding = "async";
        nextImage.onload = () => resolve(nextImage);
        nextImage.onerror = () => reject(new Error("Nu am putut rasteriza unul dintre grafice pentru exportul PDF."));
        nextImage.src = blobUrl;
      });

      const scale = 2;
      const canvas = document.createElement("canvas");
      canvas.width = renderWidth * scale;
      canvas.height = renderHeight * scale;

      const context = canvas.getContext("2d");
      if (!context) {
        throw new Error("Browserul nu a putut pregati imaginea pentru export.");
      }

      context.scale(scale, scale);
      context.drawImage(image, 0, 0, renderWidth, renderHeight);
      return canvas.toDataURL("image/png");
    } finally {
      URL.revokeObjectURL(blobUrl);
    }
  } finally {
    sandbox.remove();
  }
}

async function collectPdfChartSnapshots() {
  const chartCards = Array.from(elements.chartsGrid.querySelectorAll(".chart-card"));
  if (!chartCards.length) return [];

  const viewportWidth = document.documentElement.clientWidth || 0;
  const exportWidth = Math.max(920, Math.min(1120, viewportWidth > 0 ? viewportWidth - 120 : 1040));
  const snapshots = [];

  for (const card of chartCards) {
    snapshots.push(await captureElementAsPngDataUrl(card, exportWidth));
  }

  return snapshots;
}

function renderSummary(summary) {
  if (!summary) {
    elements.summaryCards.replaceChildren();
    return;
  }

  const metrics = [
    ["Cost initial", `${formatNumber(summary.initial_cost)} UM`, "solutia Nord-Vest"],
    ["Cost optim", `${formatNumber(summary.optimal_cost)} UM`, "dupa iteratiile MODI"],
    ["Iteratii", String(summary.iteration_count), ""],
    ["Verdict", summary.verdict, summary.balanced ? "sistem echilibrat" : "sistem dezechilibrat"],
    ["Risc", `${formatNumber(summary.risk_score)}/100`, "scor obtinut din interpretarea ML"],
  ];

  const fragment = document.createDocumentFragment();
  metrics.forEach(([label, value, subvalue]) => {
    const card = document.createElement("article");
    card.className = "metric-card";
    card.innerHTML = `
      <div class="label">${label}</div>
      <div class="value">${value}</div>
      ${subvalue ? `<div class="subvalue">${subvalue}</div>` : ""}
    `;
    fragment.appendChild(card);
  });

  elements.summaryCards.replaceChildren(fragment);
}

function createSvgElement(tagName, attributes = {}) {
  const element = document.createElementNS(SVG_NS, tagName);
  Object.entries(attributes).forEach(([key, value]) => {
    element.setAttribute(key, String(value));
  });
  return element;
}

function appendSvgTextLines({ svg, x, y, lines, className, lineHeight = 14, anchor = "middle" }) {
  const group = createSvgElement("g", {
    class: className,
  });
  const totalHeight = (lines.length - 1) * lineHeight;
  const startY = y - totalHeight / 2;

  lines.forEach((line, index) => {
    const text = createSvgElement("text", {
      x,
      y: startY + index * lineHeight,
      class: `${className}__line ${className}__line--${index}`,
      "text-anchor": anchor,
    });
    text.textContent = line;
    group.appendChild(text);
  });

  svg.appendChild(group);
  return group;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function splitLabelLines(label, maxChars = 18, maxLines = 2) {
  const words = String(label || "").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return ["-"];

  const lines = [];
  let current = "";

  words.forEach((word) => {
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxChars || !current) {
      current = next;
      return;
    }
    lines.push(current);
    current = word;
  });

  if (current) lines.push(current);

  if (lines.length <= maxLines) return lines;

  const merged = lines.slice(0, maxLines);
  const tail = lines.slice(maxLines - 1).join(" ");
  merged[maxLines - 1] = tail.length > maxChars ? `${tail.slice(0, maxChars - 1)}…` : tail;
  return merged;
}

function formatSingleLineLabel(label, maxChars = 24) {
  const clean = String(label || "").trim();
  if (!clean) return "-";
  return clean.length > maxChars ? `${clean.slice(0, maxChars - 1)}…` : clean;
}

function createChartCard({ kicker, title, description, stage, footer }) {
  const card = document.createElement("article");
  card.className = "chart-card";

  const copy = document.createElement("div");
  copy.className = "chart-copy";
  copy.innerHTML = `
    <span class="chart-kicker">${kicker}</span>
    <h3>${title}</h3>
    <p>${description}</p>
  `;

  card.appendChild(copy);
  card.appendChild(stage);
  if (footer) {
    card.appendChild(footer);
  }
  return card;
}

function activateChartAnimations(card) {
  if (!card || card.classList.contains("is-visible")) return;
  card.classList.add("is-visible");
}

function setupChartVisibilityObserver() {
  if (chartVisibilityObserver) {
    chartVisibilityObserver.disconnect();
    chartVisibilityObserver = null;
  }

  const chartCards = Array.from(elements.chartsGrid.querySelectorAll(".chart-card"));
  if (!chartCards.length) return;

  if (!("IntersectionObserver" in window)) {
    chartCards.forEach(activateChartAnimations);
    return;
  }

  chartVisibilityObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        activateChartAnimations(entry.target);
        chartVisibilityObserver?.unobserve(entry.target);
      });
    },
    {
      root: null,
      threshold: 0.35,
      rootMargin: "0px 0px -8% 0px",
    },
  );

  chartCards.forEach((card) => chartVisibilityObserver.observe(card));
}

function createMetricPill(label, value, tone = "default") {
  const pill = document.createElement("div");
  pill.className = `chart-pill chart-pill-${tone}`;
  pill.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
  return pill;
}

function splitIterationMessage(message) {
  return String(message || "")
    .split(/(?<=\.)\s+/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function createCostEvolutionStage(states) {
  const stage = document.createElement("div");
  stage.className = "chart-stage chart-stage-cost";

  const width = 920;
  const height = 330;
  const padding = { top: 26, right: 24, bottom: 54, left: 72 };
  const svg = createSvgElement("svg", {
    class: "chart-svg chart-svg-cost",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": "Grafic cu evoluția costului total pe iterații",
  });

  const defs = createSvgElement("defs");
  const gradient = createSvgElement("linearGradient", {
    id: "chartAreaGradient",
    x1: "0%",
    y1: "0%",
    x2: "0%",
    y2: "100%",
  });
  gradient.appendChild(createSvgElement("stop", { offset: "0%", "stop-color": "#62d4ca", "stop-opacity": "0.34" }));
  gradient.appendChild(createSvgElement("stop", { offset: "100%", "stop-color": "#62d4ca", "stop-opacity": "0.02" }));
  defs.appendChild(gradient);
  svg.appendChild(defs);

  const iterations = states.map((item) => item.iteration);
  const costs = states.map((item) => Number(item.transport_cost || 0));
  const minCost = Math.min(...costs);
  const maxCost = Math.max(...costs);
  const range = Math.max(maxCost - minCost, Math.max(maxCost, 1) * 0.08);
  const chartBottom = height - padding.bottom;
  const chartTop = padding.top;
  const chartLeft = padding.left;
  const chartRight = width - padding.right;
  const chartWidth = chartRight - chartLeft;
  const chartHeight = chartBottom - chartTop;
  const baseline = Math.max(0, minCost - range * 0.22);
  const denominator = Math.max(maxCost - baseline, 1);

  const pointFor = (cost, index) => {
    const x = chartLeft + (iterations.length === 1 ? chartWidth / 2 : (index / (iterations.length - 1)) * chartWidth);
    const y = chartBottom - ((cost - baseline) / denominator) * chartHeight;
    return { x, y };
  };

  for (let tickIndex = 0; tickIndex <= 4; tickIndex += 1) {
    const value = baseline + (denominator / 4) * tickIndex;
    const y = chartBottom - (chartHeight / 4) * tickIndex;
    const grid = createSvgElement("line", {
      x1: chartLeft,
      y1: y,
      x2: chartRight,
      y2: y,
      class: "chart-grid-line",
    });
    svg.appendChild(grid);

    const label = createSvgElement("text", {
      x: chartLeft - 14,
      y: y + 4,
      class: "chart-axis-text chart-axis-text-left",
    });
    label.textContent = formatNumber(value);
    svg.appendChild(label);
  }

  const points = costs.map((cost, index) => pointFor(cost, index));
  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${chartBottom} L ${points[0].x} ${chartBottom} Z`;

  const area = createSvgElement("path", {
    d: areaPath,
    class: "chart-area-path",
  });
  svg.appendChild(area);

  const line = createSvgElement("path", {
    d: linePath,
    class: "chart-line-path",
  });
  svg.appendChild(line);

  points.forEach((point, index) => {
    const group = createSvgElement("g", {
      class: "chart-point-group",
      style: `animation-delay:${index * 110}ms`,
    });
    const halo = createSvgElement("circle", {
      cx: point.x,
      cy: point.y,
      r: index === points.length - 1 ? 10 : 7,
      class: index === points.length - 1 ? "chart-point chart-point-highlight" : "chart-point",
    });
    const center = createSvgElement("circle", {
      cx: point.x,
      cy: point.y,
      r: index === points.length - 1 ? 4.5 : 3.5,
      class: "chart-point-core",
    });
    const valueText = createSvgElement("text", {
      x: point.x,
      y: point.y - 14,
      class: "chart-value-text",
    });
    valueText.textContent = formatNumber(costs[index]);

    const axisText = createSvgElement("text", {
      x: point.x,
      y: chartBottom + 28,
      class: "chart-axis-text",
    });
    axisText.textContent = `I${iterations[index]}`;

    group.appendChild(halo);
    group.appendChild(center);
    group.appendChild(valueText);
    svg.appendChild(group);
    svg.appendChild(axisText);
  });

  const wrap = document.createElement("div");
  wrap.className = "chart-frame chart-frame-svg";
  wrap.appendChild(svg);
  stage.appendChild(wrap);

  requestAnimationFrame(() => {
    const lineLength = line.getTotalLength();
    line.style.setProperty("--path-length", `${lineLength}`);
    const areaLength = area.getTotalLength();
    area.style.setProperty("--path-length", `${areaLength}`);
  });

  return stage;
}

function createCoverageStage(interpretation) {
  const stage = document.createElement("div");
  stage.className = "chart-stage chart-stage-bars";

  const wrap = document.createElement("div");
  wrap.className = "chart-frame chart-frame-bars";

  const rows = interpretation.acoperire_destinatii || [];

  rows.forEach((item, index) => {
    const need = Number(item.necesar || 0);
    const covered = Number(item.acoperit || 0);
    const coverage = Number(item.acoperire_procente || 0);
    const deficit = Number(item.deficit || 0);
    const fillRatio = need > 0 ? clamp(covered / need, 0, 1) : covered > 0 ? 1 : 0;

    const row = document.createElement("div");
    row.className = "coverage-row";
    row.style.setProperty("--delay", `${index * 90}ms`);

    const header = document.createElement("div");
    header.className = "coverage-row-header";
    header.innerHTML = `
      <div>
        <strong>${item.destinatie}</strong>
        <span>Acoperire ${formatNumber(coverage)}%</span>
      </div>
      <div class="coverage-row-values">
        <span>Alocat ${formatNumber(covered)}</span>
        <span>Necesar ${formatNumber(need)}</span>
        <span class="${deficit > 0 ? "is-warning" : "is-ok"}">${deficit > 0 ? `Deficit ${formatNumber(deficit)}` : "Fără deficit"}</span>
      </div>
    `;

    const track = document.createElement("div");
    track.className = "coverage-track";

    const needBar = document.createElement("div");
    needBar.className = "coverage-need-bar";
    needBar.style.setProperty("--target-width", "100%");

    const fill = document.createElement("div");
    fill.className = deficit > 0 ? "coverage-fill is-warning" : "coverage-fill";
    fill.style.setProperty("--target-width", `${fillRatio * 100}%`);

    track.appendChild(needBar);
    track.appendChild(fill);
    row.appendChild(header);
    row.appendChild(track);
    wrap.appendChild(row);
  });

  stage.appendChild(wrap);
  return stage;
}

function createNetworkStage(states, interpretation) {
  const finalState = states.at(-1);
  const stage = document.createElement("div");
  stage.className = "chart-stage chart-stage-network";

  const sourceRows = finalState.rows.filter((row) => !row.is_dummy).map((row) => ({
    ...row,
    labelLines: [
      formatSingleLineLabel(row.label, 26),
      "",
      row.supply_display ? `Disponibil ${row.supply_display}` : "Sursă activă",
    ],
  }));
  const destinationColumns = finalState.columns.filter((column) => !column.is_dummy).map((column) => ({
    ...column,
    labelLines: [
      formatSingleLineLabel(column.label, 24),
      "",
      column.demand_display ? `Necesar ${column.demand_display}` : "Destinație activă",
    ],
  }));
  const flows = [];

  sourceRows.forEach((row) => {
    row.cells.forEach((cell) => {
      if (cell.is_dummy || !cell.allocation || Number(cell.allocation.real || 0) <= 0) return;
      const destination = destinationColumns.find((column) => column.index === Number(cell.key.split(":")[1]));
      if (!destination) return;
      flows.push({
        source: row.label,
        destination: destination.label,
        value: Number(cell.allocation.real || 0),
      });
    });
  });

  const maxNodes = Math.max(sourceRows.length, destinationColumns.length, 1);
  const maxSourceLines = Math.max(...sourceRows.map((row) => row.labelLines.length), 3);
  const maxDestinationLines = Math.max(...destinationColumns.map((column) => column.labelLines.length), 3);
  const maxLinesPerCard = Math.max(maxSourceLines, maxDestinationLines, 3);
  const cardHeight = 28 + maxLinesPerCard * 14;
  const slotHeight = Math.max(92, cardHeight + 18);
  const width = 920;
  const height = Math.max(440, 154 + maxNodes * slotHeight);
  const panelY = 42;
  const panelWidth = 246;
  const sourcePanelX = 40;
  const destinationPanelX = width - 286;
  const innerCardX = 62;
  const cardWidth = 202;
  const sourceCardX = innerCardX;
  const destinationCardX = width - innerCardX - cardWidth;
  const sourceAnchorX = sourceCardX + cardWidth;
  const destinationAnchorX = destinationCardX;
  const contentTop = 110;
  const maxFlow = Math.max(1, ...flows.map((flow) => flow.value));
  const tumorDestination = interpretation?.tumora?.destinatie || "";
  const sourceCenterY = (_label, index) => contentTop + index * slotHeight + slotHeight / 2;
  const destinationCenterY = (_label, index) => contentTop + index * slotHeight + slotHeight / 2;

  const positions = {
    source: new Map(
      sourceRows.map((row, index) => [
        row.label,
        sourceRows.length === 1 ? height / 2 : sourceCenterY(row.label, index),
      ]),
    ),
    destination: new Map(
      destinationColumns.map((column, index) => [
        column.label,
        destinationColumns.length === 1 ? height / 2 : destinationCenterY(column.label, index),
      ]),
    ),
  };

  const svg = createSvgElement("svg", {
    class: "chart-svg chart-svg-network",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": "Hartă a rutelor active dintre surse și destinații",
  });

  const sourcePanel = createSvgElement("rect", {
    x: sourcePanelX,
    y: panelY,
    width: panelWidth,
    height: height - 84,
    rx: 28,
    class: "network-side-panel source-panel",
  });
  const destinationPanel = createSvgElement("rect", {
    x: destinationPanelX,
    y: panelY,
    width: panelWidth,
    height: height - 84,
    rx: 28,
    class: "network-side-panel destination-panel",
  });
  svg.appendChild(sourcePanel);
  svg.appendChild(destinationPanel);

  const leftLabel = createSvgElement("text", {
    x: sourcePanelX + panelWidth / 2,
    y: 76,
    class: "chart-axis-title chart-axis-title-left",
  });
  leftLabel.textContent = "Surse";
  svg.appendChild(leftLabel);

  const rightLabel = createSvgElement("text", {
    x: destinationPanelX + panelWidth / 2,
    y: 76,
    class: "chart-axis-title chart-axis-title-right",
  });
  rightLabel.textContent = "Destinații";
  svg.appendChild(rightLabel);

  flows.forEach((flow, index) => {
    const startY = positions.source.get(flow.source) ?? height / 2;
    const endY = positions.destination.get(flow.destination) ?? height / 2;
    const curvature = clamp((endY - startY) * 0.14, -52, 52);
    const path = createSvgElement("path", {
      d: `M ${sourceAnchorX} ${startY} C ${sourceAnchorX + 118} ${startY + curvature}, ${destinationAnchorX - 118} ${endY - curvature}, ${destinationAnchorX} ${endY}`,
      class: flow.destination === tumorDestination ? "network-line is-alert" : "network-line",
      "stroke-width": 2 + (flow.value / maxFlow) * 10,
      style: `animation-delay:${index * 120}ms`,
    });
    svg.appendChild(path);

    requestAnimationFrame(() => {
      const length = path.getTotalLength();
      path.style.setProperty("--path-length", `${length}`);
    });
  });

  sourceRows.forEach((row, index) => {
    const y = positions.source.get(row.label) ?? height / 2;
    const group = createSvgElement("g", {
      class: "network-node-group",
      style: `animation-delay:${index * 90}ms`,
    });
    const rect = createSvgElement("rect", {
      x: sourceCardX,
      y: y - cardHeight / 2,
      width: cardWidth,
      height: cardHeight,
      rx: 18,
      class: "network-node-card source-node-card",
    });
    group.appendChild(rect);
    appendSvgTextLines({
      svg: group,
      x: sourceCardX + cardWidth / 2,
      y,
      lines: row.labelLines,
      className: "network-node-copy source-node-copy",
      lineHeight: 14,
      anchor: "middle",
    });
    svg.appendChild(group);
  });

  destinationColumns.forEach((column, index) => {
    const y = positions.destination.get(column.label) ?? height / 2;
    const group = createSvgElement("g", {
      class: "network-node-group",
      style: `animation-delay:${index * 90 + 100}ms`,
    });
    const rect = createSvgElement("rect", {
      x: destinationCardX,
      y: y - cardHeight / 2,
      width: cardWidth,
      height: cardHeight,
      rx: 18,
      class: column.label === tumorDestination ? "network-node-card destination-node-card is-alert" : "network-node-card destination-node-card",
    });
    group.appendChild(rect);
    appendSvgTextLines({
      svg: group,
      x: destinationCardX + cardWidth / 2,
      y,
      lines: column.labelLines,
      className: "network-node-copy destination-node-copy",
      lineHeight: 14,
      anchor: "middle",
    });
    svg.appendChild(group);
  });

  const wrap = document.createElement("div");
  wrap.className = "chart-frame chart-frame-svg";
  wrap.appendChild(svg);
  stage.appendChild(wrap);
  return stage;
}

function createChartsFooter(states, interpretation) {
  const footer = document.createElement("div");
  footer.className = "chart-pill-grid";

  const finalState = states.at(-1);
  const flows = [];
  finalState.rows.forEach((row) => {
    if (row.is_dummy) return;
    row.cells.forEach((cell) => {
      if (!cell.is_dummy && cell.allocation && Number(cell.allocation.real || 0) > 0) {
        flows.push(Number(cell.allocation.real || 0));
      }
    });
  });

  footer.appendChild(createMetricPill("NUMAR ITERATII", String(states.length), "teal"));
  footer.appendChild(createMetricPill("Rute active", String(flows.length), "gold"));
  footer.appendChild(
    createMetricPill(
      "Scor risc",
      `${formatNumber(Number(interpretation?.scor_risc || 0))}/100`,
      Number(interpretation?.scor_risc || 0) >= 60 ? "rose" : "default",
    ),
  );
  return footer;
}

function renderCharts(states, interpretation) {
  if (!states || !states.length || !interpretation) {
    if (chartVisibilityObserver) {
      chartVisibilityObserver.disconnect();
      chartVisibilityObserver = null;
    }
    elements.chartsGrid.className = "charts-grid charts-stack empty-state";
    elements.chartsGrid.textContent = "Graficele apar dupa prima rulare completa a solverului.";
    return;
  }

  elements.chartsGrid.className = "charts-grid charts-stack";
  elements.chartsGrid.replaceChildren(
    createChartCard({
      kicker: "Grafic 01",
      title: "Evoluția costului total",
      description: "Curba urmărește scăderea costului după fiecare iterație, cu accent pe punctul de pornire și soluția optimă.",
      stage: createCostEvolutionStage(states),
      footer: createChartsFooter(states, interpretation),
    }),
    createChartCard({
      kicker: "Grafic 02",
      title: "Acoperirea destinațiilor",
      description: "Fiecare bară arată cât s-a distribuit față de necesar, ca să vezi rapid unde există deficit sau acoperire completă.",
      stage: createCoverageStage(interpretation),
    }),
    createChartCard({
      kicker: "Grafic 03",
      title: "Harta rutelor active",
      description: "Rețeaua evidențiază doar conexiunile care transportă efectiv flux, iar grosimea traseului arată intensitatea rutei.",
      stage: createNetworkStage(states, interpretation),
    }),
  );
  setupChartVisibilityObserver();
}

function renderInterpretation(interpretation) {
  if (!interpretation) {
    elements.interpretationPanel.className = "interpretation empty-state";
    elements.interpretationPanel.textContent =
      "Verdictul, scorul de risc si recomandarile apar aici dupa simulare.";
    return;
  }

  elements.interpretationPanel.className = "interpretation";

  const coverageRows = interpretation.acoperire_destinatii
    .map(
      (item) => `
        <tr>
          <td>${item.destinatie}</td>
          <td>${formatNumber(item.necesar)}</td>
          <td>${formatNumber(item.acoperit)}</td>
          <td>${formatNumber(item.deficit)}</td>
          <td>${formatNumber(item.acoperire_procente)}%</td>
        </tr>`,
    )
    .join("");

  const recommendations = interpretation.recomandari
    .map((recommendation) => `<li>${recommendation}</li>`)
    .join("");
  const userSummary = interpretation.rezumat_utilizator || {};
  const summaryPoints = (userSummary.puncte || [])
    .map((point) => `<li>${point}</li>`)
    .join("");

  elements.interpretationPanel.innerHTML = `
    <div class="interpretation-header">
      <div>
        <div class="section-kicker">Verdict</div>
        <div class="verdict">${interpretation.verdict}</div>
        <p>${userSummary.titlu || interpretation.regula_decizie}</p>
      </div>
      <div class="risk-pill">Scor risc: ${formatNumber(interpretation.scor_risc)}/100</div>
    </div>
    <div class="interpretation-grid">
      <div class="info-card summary-card">
        <h3>Pe scurt</h3>
        <p>${userSummary.mesaj || interpretation.regula_decizie}</p>
        <ul>${summaryPoints}</ul>
      </div>
      <div class="info-card">
        <h3>Explicatie tehnica</h3>
        <p>Regula activata: <strong>${interpretation.regula_decizie}</strong></p>
        <p>Nivel risc: <strong>${interpretation.nivel_risc || "-"}</strong></p>
        <p>Verdict AI: <strong>${interpretation.verdict}</strong></p>
      </div>
      <div class="info-card">
        <h3>Eficienta sistemului</h3>
        <p>Cost initial: <strong>${formatNumber(interpretation.eficienta.cost_initial)} UM</strong></p>
        <p>Cost optim: <strong>${formatNumber(interpretation.eficienta.cost_optim)} UM</strong></p>
        <p>Economie: <strong>${formatNumber(interpretation.eficienta.economie_efort_procente)}%</strong></p>
        <p>Oferta totala: <strong>${formatNumber(interpretation.echilibru.oferta_totala)}</strong></p>
        <p>Cerere totala: <strong>${formatNumber(interpretation.echilibru.cerere_totala)}</strong></p>
      </div>
      <div class="info-card">
        <h3>Punct de consum parazit</h3>
        <p>Detectat: <strong>${interpretation.tumora.detectata ? "Da" : "Nu"}</strong></p>
        <p>Destinatie: <strong>${interpretation.tumora.destinatie || "-"}</strong></p>
        <p>Flux primit: <strong>${formatNumber(interpretation.tumora.flux_primit)}</strong></p>
        <p>Pondere flux: <strong>${formatNumber(interpretation.tumora.pondere_flux)}%</strong></p>
        <p>Avantaj angiogenic: <strong>${interpretation.tumora.avantaj_angiogenic ? "Da" : "Nu"}</strong></p>
      </div>
      <div class="info-card">
        <h3>Acoperire pe destinatii</h3>
        <table class="coverage-table">
          <thead>
            <tr>
              <th>Destinatie</th>
              <th>Necesar</th>
              <th>Acoperit</th>
              <th>Deficit</th>
              <th>Acoperire</th>
            </tr>
          </thead>
          <tbody>${coverageRows}</tbody>
        </table>
      </div>
      <div class="info-card">
        <h3>Strategii recomandate</h3>
        <ol>${recommendations}</ol>
      </div>
    </div>
  `;
}

function renderIterationTable(iteration) {
  const table = document.createElement("table");
  table.className = "transport-table";

  const headerRow = document.createElement("tr");
  const corner = document.createElement("th");
  corner.className = "corner-cell";
  corner.textContent = "u / v";
  headerRow.appendChild(corner);

  iteration.columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.className = "column-header";
    cell.innerHTML = `${column.label}<small>v = ${column.v_display}</small>`;
    headerRow.appendChild(cell);
  });

  const sumHeader = document.createElement("th");
  sumHeader.className = "sum-header";
  sumHeader.innerHTML = "&Sigma; Disponibil";
  headerRow.appendChild(sumHeader);
  table.appendChild(headerRow);

  iteration.rows.forEach((row) => {
    const rowElement = document.createElement("tr");

    const rowHeader = document.createElement("th");
    rowHeader.className = "row-header";
    rowHeader.innerHTML = `${row.label}<small>u = ${row.u_display}</small>`;
    rowElement.appendChild(rowHeader);

    row.cells.forEach((cell) => {
      const cellElement = document.createElement("td");
      const wrapper = document.createElement("div");
      wrapper.className = "transport-cell";
      if (cell.is_pivot) wrapper.classList.add("pivot");
      if (cell.is_cycle && !cell.is_pivot) wrapper.classList.add("cycle");
      if (cell.is_dummy) wrapper.classList.add("dummy");

      const allocationHtml = cell.allocation
        ? `<div class="cell-allocation">${cell.allocation.display}${
            cell.cycle_sign ? `<span class="cell-sign">(${cell.cycle_sign})</span>` : ""
          }</div>`
        : cell.delta !== null && cell.delta !== undefined && cell.delta < 0
          ? `<div class="cell-delta">(${formatNumber(cell.delta)})</div>`
          : "";

      wrapper.innerHTML = `
        <div class="cell-cost">${formatNumber(cell.cost)}</div>
        ${allocationHtml}
      `;

      cellElement.appendChild(wrapper);
      rowElement.appendChild(cellElement);
    });

    const sumCell = document.createElement("td");
    sumCell.className = "sum-cell";
    sumCell.textContent = row.supply_display;
    rowElement.appendChild(sumCell);
    table.appendChild(rowElement);
  });

  const demandRow = document.createElement("tr");
  const demandLabel = document.createElement("th");
  demandLabel.className = "row-sum-label";
  demandLabel.innerHTML = "&Sigma; Necesar";
  demandRow.appendChild(demandLabel);

  iteration.columns.forEach((column) => {
    const demandCell = document.createElement("td");
    demandCell.className = "sum-cell";
    demandCell.textContent = column.demand_display;
    demandRow.appendChild(demandCell);
  });

  const totalCell = document.createElement("td");
  totalCell.className = "sum-cell ok";
  totalCell.textContent = iteration.total_supply_display;
  demandRow.appendChild(totalCell);
  table.appendChild(demandRow);

  return table;
}

function renderIterations(states) {
  if (!states) {
    elements.iterationsList.className = "iterations-list empty-state";
    elements.iterationsList.textContent =
      "Fiecare iteratie MODI va fi afisata aici, cu matrice, costuri marginale si circuit de compensare.";
    return;
  }

  elements.iterationsList.className = "iterations-list";
  elements.iterationsList.replaceChildren(
    ...states.map((iteration) => {
      const details = document.createElement("details");
      details.className = "iteration-card";
      details.open = iteration.iteration === 0 || iteration.is_optimal;

      const summary = document.createElement("summary");
      summary.className = "iteration-summary";
      summary.innerHTML = `
        <div class="iteration-index">${iteration.iteration}</div>
        <div>
          <div class="iteration-title">Iteratia ${iteration.iteration}${iteration.iteration === 0 ? " (N-V)" : ""}</div>
          <div class="iteration-meta">Cost transport: ${formatNumber(iteration.transport_cost)} UM</div>
        </div>
        <div class="iteration-pill">${iteration.is_optimal ? "Solutie optima" : "In curs de optimizare"}</div>
      `;

      const body = document.createElement("div");
      body.className = "iteration-body";

      const message = document.createElement("div");
      message.className = "iteration-message";
      const messageLines = splitIterationMessage(iteration.message);
      if (messageLines.length <= 1) {
        message.textContent = iteration.message;
      } else {
        message.replaceChildren(
          ...messageLines.map((line) => {
            const row = document.createElement("div");
            row.className = "iteration-message-line";
            row.textContent = line;
            return row;
          }),
        );
      }
      body.appendChild(message);

      const tableWrap = document.createElement("div");
      tableWrap.className = "transport-table-wrap";
      tableWrap.appendChild(renderIterationTable(iteration));
      body.appendChild(tableWrap);

      details.appendChild(summary);
      details.appendChild(body);
      return details;
    }),
  );
}

async function loadSample() {
  setStatus("Incarc exemplul de lucru din proiect...");
  if (!apiBase) {
    throw new Error("Pagina a fost deschisa direct din fisier. Porneste webapp.py si acceseaza site-ul prin http://127.0.0.1:8000.");
  }
  const response = await fetch(`${apiBase}/sample`);
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "Nu am putut incarca exemplul.");
  }
  applyDataset(data.dataset);
  setStatus("Datele de prezentare au fost încărcate cu succes.", { autoHideMs: 2600 });
}

function rebuildMatrix() {
  syncDatasetMeta();
  const rows = Number(elements.rowsInput.value);
  const cols = Number(elements.colsInput.value);

  if (!Number.isInteger(rows) || rows <= 0 || !Number.isInteger(cols) || cols <= 0) {
    throw new Error("m si n trebuie sa fie numere intregi pozitive.");
  }

  const nextDataset = makeDefaultDataset(rows, cols);
  if (state.dataset) {
    nextDataset.title = state.dataset.title;
    nextDataset.scenario = state.dataset.scenario;
    nextDataset.notes = state.dataset.notes;

    for (let i = 0; i < Math.min(rows, state.dataset.supply.length); i++) {
      nextDataset.supply[i] = state.dataset.supply[i];
      nextDataset.source_labels[i] = state.dataset.source_labels[i];
      for (let j = 0; j < Math.min(cols, state.dataset.demand.length); j++) {
        nextDataset.cost_matrix[i][j] = state.dataset.cost_matrix[i][j];
      }
    }
    for (let j = 0; j < Math.min(cols, state.dataset.demand.length); j++) {
      nextDataset.demand[j] = state.dataset.demand[j];
      nextDataset.destination_labels[j] = state.dataset.destination_labels[j];
    }
  }

  applyDataset(nextDataset);
  setStatus("Matrice noua generata. Completeaza costurile, capacitatile si necesarul.");
}

async function solve() {
  const payload = collectDataset();
  setStatus("Rulez solverul problemei de transport si pregatesc interpretarea vizuala...");
  const data = await requestJson(`${apiBase}/solve`, payload);
  state.result = data;
  renderSummary(data.summary);
  renderCharts(data.states, data.interpretation);
  renderInterpretation(data.interpretation);
  renderIterations(data.states);
  setStatus(
    `Solver finalizat. Cost optim ${formatNumber(data.summary.optimal_cost)} UM, ${data.summary.iteration_count} iteratii MODI, verdict ${data.summary.verdict}.`,
  );
}

async function exportFile(kind) {
  const payload = collectDataset();
  if (kind === "pdf") {
    setStatus("Pregatesc exportul PDF si captez graficele reale din interfata...");
    if (state.result) {
      try {
        payload.pdf_chart_snapshots = await collectPdfChartSnapshots();
      } catch (err) {
        console.warn("Nu s-au putut capta graficele reale, se va folosi fallback-ul din backend.", err);
      }
    }
  } else {
    setStatus(`Pregatesc exportul ${kind.toUpperCase()}...`);
  }
  const { blob, filename } = await requestBlob(`${apiBase}/export/${kind}`, payload);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  setStatus(`Exportul ${filename} a fost generat.`);
}

async function importUploadedFile(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  setStatus(`Import fisier ${file.name}...`);
  const content = await file.text();
  const data = await requestJson(`${apiBase}/import`, {
    filename: file.name,
    content,
  });
  applyDataset(data.dataset);
  setStatus(`Fișierul ${file.name} a fost încărcat cu succes.`, { autoHideMs: 2600 });
  event.target.value = "";
}

async function boot() {
  if (isFileProtocol) {
    setStatus("Pagina este deschisa din fisier local. API-ul nu poate functiona asa. Porneste serverul cu start_web.bat sau cu .\\.venv\\Scripts\\python.exe webapp.py, apoi intra pe http://127.0.0.1:8000.");
  }

  syncSidebarForViewport();
  setActiveView(readStoredActiveView());
  elements.sidebarToggle.addEventListener("click", toggleSidebar);
  window.addEventListener("resize", syncSidebarForViewport);
  elements.viewButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setActiveView(button.dataset.viewTrigger);
    });
  });
  elements.sampleBtn.addEventListener("click", () => loadSample().catch(handleError));
  elements.buildBtn.addEventListener("click", () => {
    try {
      rebuildMatrix();
    } catch (error) {
      handleError(error);
    }
  });
  elements.solveBtn.addEventListener("click", () => solve().catch(handleError));
  elements.exportJsonBtn.addEventListener("click", () => exportFile("json").catch(handleError));
  elements.exportPdfBtn.addEventListener("click", () => exportFile("pdf").catch(handleError));
  elements.fileInput.addEventListener("change", (event) => importUploadedFile(event).catch(handleError));

  elements.titleInput.addEventListener("input", syncDatasetMeta);
  elements.scenarioInput.addEventListener("input", syncDatasetMeta);
  elements.notesInput.addEventListener("input", syncDatasetMeta);

  applyDataset(makeDefaultDataset(3, 5));
}

function handleError(error) {
  console.error(error);
  const message = error instanceof Error ? error.message : "A aparut o eroare necunoscuta.";
  setStatus(message);
}

boot().catch(handleError);
