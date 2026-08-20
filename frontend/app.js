import { createViewer } from "./stl-viewer.js";

const API = "/api";

const state = {
  binId: null,
  manifest: null,
  polygon: [],       // [{x, y}] in mm, item-local space
  transform: null,   // {scale, offsetX, offsetY} mm -> canvas px, fixed per review session
};

const els = {
  error: document.getElementById("error"),
  steps: {
    upload: document.getElementById("step-upload"),
    review: document.getElementById("step-review"),
    params: document.getElementById("step-params"),
    preview: document.getElementById("step-preview"),
  },
  stepLabels: document.querySelectorAll(".steps span"),
};

function showError(msg) {
  els.error.textContent = msg;
  els.error.style.display = "block";
}
function clearError() {
  els.error.style.display = "none";
}

function goToStep(name) {
  for (const [key, el] of Object.entries(els.steps)) {
    el.style.display = key === name ? "block" : "none";
  }
  els.stepLabels.forEach((el) => el.classList.toggle("active", el.dataset.step === name));
}

// ===== Step 1: Upload ===== //

document.getElementById("upload-btn").addEventListener("click", async () => {
  clearError();
  const topFile = document.getElementById("top-photo").files[0];
  const sideFile = document.getElementById("side-photo").files[0];
  if (!topFile || !sideFile) {
    showError("Please choose both a top-down and a side photo.");
    return;
  }

  const form = new FormData();
  form.append("top_photo", topFile);
  form.append("side_photo", sideFile);
  form.append("reference_size_mm", document.getElementById("marker-size").value);
  form.append("item_name", document.getElementById("item-name").value);

  const btn = document.getElementById("upload-btn");
  btn.disabled = true;
  btn.textContent = "Analyzing…";
  try {
    const res = await fetch(`${API}/photos`, { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json()).detail || "Upload failed.");
    const manifest = await res.json();
    state.binId = manifest.id;
    state.manifest = manifest;
    enterReview(manifest);
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Analyze photos";
  }
});

// ===== Step 2: Review ===== //

const canvas = document.getElementById("silhouette-canvas");
const ctx = canvas.getContext("2d");
let dragIndex = null;

function enterReview(manifest) {
  document.getElementById("top-photo-preview").src = `${API}/bins/${manifest.id}/photo/top`;
  document.getElementById("side-photo-preview").src = `${API}/bins/${manifest.id}/photo/side`;
  document.getElementById("height-input").value = manifest.height_mm?.toFixed(1) ?? "";

  state.polygon = manifest.silhouette_polygon.map((p) => ({ x: p.x, y: p.y }));
  state.transform = computeTransform(state.polygon);
  drawSilhouette();
  goToStep("review");
}

function computeTransform(points) {
  const pad = 40;
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = Math.max(maxX - minX, 1), h = Math.max(maxY - minY, 1);
  const scale = Math.min((canvas.width - 2 * pad) / w, (canvas.height - 2 * pad) / h);
  return {
    scale,
    offsetX: pad - minX * scale + ((canvas.width - 2 * pad) - w * scale) / 2,
    offsetY: pad - minY * scale + ((canvas.height - 2 * pad) - h * scale) / 2,
  };
}

function mmToPx(p) {
  return { x: p.x * state.transform.scale + state.transform.offsetX, y: p.y * state.transform.scale + state.transform.offsetY };
}
function pxToMm(p) {
  return { x: (p.x - state.transform.offsetX) / state.transform.scale, y: (p.y - state.transform.offsetY) / state.transform.scale };
}

function drawSilhouette() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const pts = state.polygon.map(mmToPx);

  ctx.beginPath();
  pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.closePath();
  ctx.fillStyle = "rgba(79, 140, 255, 0.15)";
  ctx.fill();
  ctx.strokeStyle = "#4f8cff";
  ctx.lineWidth = 2;
  ctx.stroke();

  pts.forEach((p) => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
    ctx.fillStyle = "#e6e8eb";
    ctx.fill();
    ctx.strokeStyle = "#4f8cff";
    ctx.stroke();
  });
}

function nearestPointIndex(pos, maxDist = 10) {
  const pts = state.polygon.map(mmToPx);
  let best = -1, bestDist = maxDist;
  pts.forEach((p, i) => {
    const d = Math.hypot(p.x - pos.x, p.y - pos.y);
    if (d < bestDist) { bestDist = d; best = i; }
  });
  return best;
}

function nearestEdgeInsertion(pos) {
  const pts = state.polygon.map(mmToPx);
  let best = -1, bestDist = 12;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    const d = distToSegment(pos, a, b);
    if (d < bestDist) { bestDist = d; best = i; }
  }
  return best;
}

function distToSegment(p, a, b) {
  const l2 = (a.x - b.x) ** 2 + (a.y - b.y) ** 2;
  if (l2 === 0) return Math.hypot(p.x - a.x, p.y - a.y);
  let t = ((p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y)) / l2;
  t = Math.max(0, Math.min(1, t));
  const proj = { x: a.x + t * (b.x - a.x), y: a.y + t * (b.y - a.y) };
  return Math.hypot(p.x - proj.x, p.y - proj.y);
}

canvas.addEventListener("mousedown", (e) => {
  const pos = { x: e.offsetX, y: e.offsetY };
  dragIndex = nearestPointIndex(pos);
});
canvas.addEventListener("mousemove", (e) => {
  if (dragIndex === null) return;
  const mm = pxToMm({ x: e.offsetX, y: e.offsetY });
  state.polygon[dragIndex] = mm;
  drawSilhouette();
});
window.addEventListener("mouseup", () => { dragIndex = null; });

canvas.addEventListener("dblclick", (e) => {
  const pos = { x: e.offsetX, y: e.offsetY };
  const removeIdx = nearestPointIndex(pos);
  if (removeIdx !== -1 && state.polygon.length > 3) {
    state.polygon.splice(removeIdx, 1);
    drawSilhouette();
    return;
  }
  const edgeIdx = nearestEdgeInsertion(pos);
  if (edgeIdx !== -1) {
    state.polygon.splice(edgeIdx + 1, 0, pxToMm(pos));
    drawSilhouette();
  }
});

document.getElementById("review-continue-btn").addEventListener("click", async () => {
  clearError();
  try {
    await fetch(`${API}/photos/${state.binId}/silhouette`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.polygon),
    });
    const heightMm = parseFloat(document.getElementById("height-input").value);
    await fetch(`${API}/photos/${state.binId}/height?height_mm=${heightMm}`, { method: "PUT" });

    const res = await fetch(`${API}/bins/${state.binId}/params`, { method: "POST" });
    const manifest = await res.json();
    state.manifest = manifest;
    enterParams(manifest);
  } catch (e) {
    showError(e.message || "Couldn't save your edits.");
  }
});

// ===== Step 3: Bin params ===== //

function enterParams(manifest) {
  document.getElementById("grid-x").value = manifest.grid_x;
  document.getElementById("grid-y").value = manifest.grid_y;
  document.getElementById("bin-height").value = manifest.bin_height_units;
  document.getElementById("clearance").value = manifest.clearance_mm;
  goToStep("params");
}

document.getElementById("generate-btn").addEventListener("click", async () => {
  clearError();
  const btn = document.getElementById("generate-btn");
  btn.disabled = true;
  btn.textContent = "Rendering…";
  try {
    const params = new URLSearchParams({
      grid_x: document.getElementById("grid-x").value,
      grid_y: document.getElementById("grid-y").value,
      bin_height_units: document.getElementById("bin-height").value,
      clearance_mm: document.getElementById("clearance").value,
    });
    const res = await fetch(`${API}/bins/${state.binId}/generate?${params}`, { method: "POST" });
    if (!res.ok) throw new Error((await res.json()).detail || "Generation failed.");
    const manifest = await res.json();
    state.manifest = manifest;
    await enterPreview(manifest);
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate bin";
  }
});

// ===== Step 4: Preview ===== //

let viewer = null;

async function enterPreview(manifest) {
  goToStep("preview");
  const container = document.getElementById("viewer-container");
  if (!viewer) viewer = createViewer(container);
  const stlUrl = `${API}/bins/${manifest.id}/stl`;
  await viewer.loadSTL(stlUrl);
  document.getElementById("download-link").href = stlUrl;
}

document.getElementById("start-over-btn").addEventListener("click", () => {
  state.binId = null;
  state.manifest = null;
  state.polygon = [];
  document.getElementById("top-photo").value = "";
  document.getElementById("side-photo").value = "";
  document.getElementById("item-name").value = "";
  clearError();
  goToStep("upload");
});
