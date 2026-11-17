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

function makeTable(title, rows, columns) {
  const wrap = el("div", undefined, "scroll");
  const table = el("table");
  table.appendChild(el("caption", title));
  const head = el("tr");
  for (const c of columns) {
    const th = el("th", c);
    th.scope = "col";
    head.appendChild(th);
  }
  const thead = el("thead");
  thead.appendChild(head);
  table.appendChild(thead);
  const body = el("tbody");
  for (const r of rows) {
    const tr = el("tr");
    for (const c of columns) tr.appendChild(el("td", String(r[c])));
    body.appendChild(tr);
  }
  table.appendChild(body);
  wrap.appendChild(table);
  return wrap;
}

function render(data) {
  const checks = document.getElementById("checks");
  checks.replaceChildren();
  for (const c of data.checks) {
    const li = el("li");
    li.appendChild(el("strong", c.ok ? "PASS" : "FAIL", c.ok ? "pass" : "fail"));
    li.appendChild(el("span", " " + c.rule));
    for (const m of c.messages) li.appendChild(el("div", m));
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
    tables.appendChild(makeTable(title, t.preview, cols));
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
    const bytes = proxy.toJs();
    proxy.destroy();
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
