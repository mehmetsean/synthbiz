"use strict";

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/";
const statusEl = document.getElementById("status");
const generateBtn = document.getElementById("generate");
const downloadBtn = document.getElementById("download");
let demo = null;
let lastArgs = null;

function setStatus(text) {
  statusEl.textContent = text;
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function readInputs() {
  return [
    Number(document.getElementById("seed").value),
    Number(document.getElementById("months").value),
    document.getElementById("size").value,
    Number(document.getElementById("rate").value),
  ];
}

function formatDollars(value) {
  const cents = BigInt(value);
  const abs = cents < 0n ? -cents : cents;
  const dollars = (abs / 100n).toString().replace(/\B(?=(\d{3})+$)/g, ",");
  const rest = String(abs % 100n).padStart(2, "0");
  return (cents < 0n ? "-" : "") + "$" + dollars + "." + rest;
}

const LONG_TEXT = 60;
const WRAP_TEXT = 24;

function makeCell(value, isMoney) {
  const text = String(value);
  const chars = Array.from(text);
  if (isMoney && /^-?\d+$/.test(text)) return el("td", formatDollars(text), "num");
  const td = el("td");
  if (chars.length <= LONG_TEXT) {
    td.textContent = text;
    if (chars.length > WRAP_TEXT) td.className = "wrap";
    return td;
  }
  td.className = "long";
  const box = el("details");
  box.appendChild(el("summary", chars.slice(0, LONG_TEXT).join("") + "..."));
  box.appendChild(el("p", text));
  td.appendChild(box);
  return td;
}

function watchHint(wrap, table, hint) {
  const update = () => {
    hint.hidden = wrap.scrollWidth <= wrap.clientWidth;
  };
  const observer = new ResizeObserver(update);
  observer.observe(wrap);
  observer.observe(table);
}

function makeTable(title, rows, columns, money) {
  const moneyCols = new Set(money || []);
  const box = el("div", undefined, "table-box");
  const hint = el("p", "Scroll sideways to see all columns.", "hint");
  hint.hidden = true;
  box.appendChild(hint);
  const wrap = el("div", undefined, "scroll");
  wrap.tabIndex = 0;
  wrap.setAttribute("role", "region");
  wrap.setAttribute("aria-label", title);
  const table = el("table");
  table.appendChild(el("caption", title));
  const head = el("tr");
  for (const c of columns) {
    const th = el("th", c, moneyCols.has(c) ? "num" : undefined);
    th.scope = "col";
    head.appendChild(th);
  }
  const thead = el("thead");
  thead.appendChild(head);
  table.appendChild(thead);
  const body = el("tbody");
  for (const r of rows) {
    const tr = el("tr");
    for (const c of columns) tr.appendChild(makeCell(r[c], moneyCols.has(c)));
    body.appendChild(tr);
  }
  table.appendChild(body);
  wrap.appendChild(table);
  box.appendChild(wrap);
  watchHint(wrap, table, hint);
  return box;
}

const SVG_NS = "http://www.w3.org/2000/svg";

function svg(tag, attrs, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, String(v));
  if (text !== undefined) node.textContent = text;
  return node;
}

function countByType(labels) {
  const counts = {};
  for (const l of labels) counts[l.anomaly_type] = (counts[l.anomaly_type] || 0) + 1;
  return Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function makeChart(rows) {
  const rowH = 28;
  const labelW = Math.max(...rows.map((r) => r[0].length)) * 7 + 8;
  const barMax = 110;
  const width = labelW + barMax + 40;
  const height = rows.length * rowH + 8;
  const max = Math.max(...rows.map((r) => r[1]));
  const chart = svg("svg", {
    class: "chart",
    viewBox: "0 0 " + width + " " + height,
    width: width,
    height: height,
  });
  chart.setAttribute("role", "img");
  chart.setAttribute("aria-labelledby", "chart-title chart-desc");
  chart.appendChild(svg("title", { id: "chart-title" }, "Planted anomalies by type"));
  const summary = rows.map((r) => r[0] + " " + r[1]).join(", ");
  chart.appendChild(svg("desc", { id: "chart-desc" }, "Bar chart. " + summary + "."));
  rows.forEach(([name, n], i) => {
    const y = i * rowH + 4;
    const w = Math.max(2, Math.round((n / max) * barMax));
    chart.appendChild(svg("text", { x: 0, y: y + 17 }, name));
    chart.appendChild(svg("rect", { class: "bar", x: labelW, y: y, width: w, height: 20, rx: 3 }));
    chart.appendChild(svg("text", { x: labelW + w + 6, y: y + 17 }, String(n)));
  });
  return chart;
}

function renderSummary(data) {
  const names = Object.keys(data.tables);
  const rows = names.reduce((sum, n) => sum + data.tables[n].rows, 0);
  const passed = data.checks.filter((c) => c.ok).length;
  const items = [
    [rows.toLocaleString("en-US"), "total rows"],
    [String(names.length), "tables"],
    [String(data.anomaly_count), "planted anomalies"],
    [passed + " of " + data.checks.length, "checks passed"],
  ];
  const list = document.getElementById("summary");
  list.replaceChildren();
  for (const [value, label] of items) {
    const li = el("li");
    li.appendChild(el("span", value, "value"));
    li.appendChild(el("span", label, "label"));
    list.appendChild(li);
  }
}

function renderChart(data) {
  const box = document.getElementById("chart");
  box.replaceChildren();
  const rows = countByType(data.labels);
  if (rows.length === 0) {
    box.appendChild(el("p", "No anomalies planted. Raise the anomaly rate to see a chart."));
    return;
  }
  box.appendChild(makeChart(rows));
  const asTable = rows.map(([name, n]) => ({ anomaly_type: name, count: n }));
  box.appendChild(makeTable("Anomaly counts by type", asTable, ["anomaly_type", "count"]));
}

function render(data) {
  renderSummary(data);
  renderChart(data);
  const checks = document.getElementById("checks");
  checks.replaceChildren();
  for (const c of data.checks) {
    const li = el("li");
    li.appendChild(el("strong", c.ok ? "[PASS]" : "[FAIL]", "mark " + (c.ok ? "pass" : "fail")));
    li.appendChild(el("span", c.rule));
    for (const m of c.messages) li.appendChild(el("div", m, "msg"));
    checks.appendChild(li);
  }
  const labels = document.getElementById("labels");
  labels.replaceChildren();
  document.getElementById("labels-title").textContent =
    "Labels (" + data.anomaly_count + " planted anomalies)";
  if (data.labels.length > 0) {
    const cols = ["table", "row_id", "anomaly_type", "details"];
    labels.appendChild(makeTable("labels.csv", data.labels, cols));
  } else {
    labels.appendChild(el("p", "No anomalies planted."));
  }
  const tables = document.getElementById("tables");
  tables.replaceChildren();
  for (const [name, t] of Object.entries(data.tables)) {
    const cols = t.preview.length > 0 ? Object.keys(t.preview[0]) : [];
    const title = name + " (" + t.rows + " rows, first " + t.preview.length + ")";
    tables.appendChild(makeTable(title, t.preview, cols, t.money));
  }
  document.getElementById("results").hidden = false;
}

async function generate(event) {
  event.preventDefault();
  generateBtn.disabled = true;
  downloadBtn.disabled = true;
  setStatus("Generating.");
  await new Promise((resolve) => setTimeout(resolve, 20));
  try {
    const args = readInputs();
    const data = JSON.parse(demo.run_demo(...args));
    lastArgs = args;
    render(data);
    downloadBtn.disabled = false;
    setStatus("Done. " + data.anomaly_count + " anomalies planted.");
  } catch (e) {
    setStatus("Error: " + String(e.message || e).split("\n").slice(-2).join(" "));
  }
  generateBtn.disabled = false;
}

function download() {
  if (!lastArgs) return;
  try {
    const proxy = demo.demo_zip(...lastArgs);
    let bytes;
    try {
      const buf = proxy.getBuffer();
      bytes = buf.data.slice();
      buf.release();
    } finally {
      proxy.destroy();
    }
    const blob = new Blob([bytes], { type: "application/zip" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "synthbiz-seed" + lastArgs[0] + ".zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setStatus("Zip saved.");
  } catch (e) {
    setStatus("Error: " + String(e.message || e));
  }
}

async function start() {
  try {
    const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
    setStatus("Loading synthbiz.");
    await pyodide.loadPackage("micropip");
    const info = await (await fetch("wheel.json")).json();
    const wheel = new URL(info.wheel, document.baseURI).href;
    pyodide.globals.set("wheel_url", wheel);
    await pyodide.runPythonAsync(
      "import micropip\nawait micropip.install(wheel_url, deps=False)"
    );
    demo = pyodide.pyimport("synthbiz.demo");
    generateBtn.disabled = false;
    setStatus("Ready.");
  } catch (e) {
    setStatus("Could not load the demo: " + String(e.message || e));
  }
}

document.getElementById("form").addEventListener("submit", generate);
downloadBtn.addEventListener("click", download);
start();
