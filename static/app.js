const TOOLS = [
  { id: "merge", name: "Merge", blurb: "Bind several PDFs into one", kicker: "Gather", headline: "Stack documents into one folio", lede: "Order the files, then bind. Page one of the first file stays page one." },
  { id: "split", name: "Split / demerge", blurb: "Cut ranges, explode pages, or chunk", kicker: "Cut", headline: "Take a document apart", lede: "Keep a range, split every N pages, or emit one PDF per page." },
  { id: "unlock", name: "Unlock", blurb: "Remove a known password", kicker: "Open", headline: "Decrypt a locked PDF", lede: "The password stays on this PC. The copy you download is an open file." },
  { id: "lock", name: "Lock", blurb: "AES-256 protect a copy", kicker: "Seal", headline: "Encrypt a copy", lede: "Set a password. Bindery never stores it after the run." },
  { id: "rotate", name: "Rotate", blurb: "Turn selected pages", kicker: "Turn", headline: "Rotate pages", lede: "Select pages in the filmstrip, or rotate the whole document." },
  { id: "drop", name: "Drop pages", blurb: "Remove selected leaves", kicker: "Trim", headline: "Delete pages", lede: "Select the pages to discard. The rest is saved as a new PDF." },
  { id: "reorder", name: "Reorder", blurb: "Shuffle page order", kicker: "Arrange", headline: "Restack the pages", lede: "Use the order field as a 1-based sequence covering every page once." },
  { id: "compress", name: "Compress", blurb: "Fit a size ceiling", kicker: "Press", headline: "Fit a size ceiling", lede: "Leave the ceiling blank for a lossless clean. Set a size and Bindery uses the gentlest image pass that still fits." },
  { id: "watermark", name: "Watermark", blurb: "Stamp quiet overlay text", kicker: "Mark", headline: "Watermark every page", lede: "A centered overlay, local only. Use for DRAFT, CONFIDENTIAL, or a name." },
  { id: "text", name: "Extract text", blurb: "Plain text from each page", kicker: "Read", headline: "Lift the words out", lede: "Digital text only — not OCR. Scans without a text layer will be sparse." },
  { id: "images", name: "Extract images", blurb: "Embedded pictures as a zip", kicker: "Lift", headline: "Pull images from the file", lede: "Each embedded image is saved in a zip. Vector-only pages yield nothing." },
  { id: "meta", name: "Details", blurb: "Title, author, keywords", kicker: "Spine", headline: "Edit document details", lede: "Write title and author into a new copy. The original file is left untouched." },
];

const state = {
  sid: null,
  tool: "merge",
  files: [],
  selected: new Set(),
  passwords: {},
  activeId: null,
};

const $ = (id) => document.getElementById(id);

function fmtBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const data = await res.json();
      msg = data.detail || JSON.stringify(data);
    } catch {
      msg = await res.text();
    }
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  const type = res.headers.get("content-type") || "";
  if (type.includes("application/json")) return res.json();
  return res;
}

function renderTools() {
  const nav = $("tools");
  nav.innerHTML = TOOLS.map((t) => `
    <button type="button" data-tool="${t.id}" class="${t.id === state.tool ? "active" : ""}">
      ${t.name}<em>${t.blurb}</em>
    </button>`).join("");
  nav.querySelectorAll("button").forEach((btn) => {
    btn.onclick = () => {
      state.tool = btn.dataset.tool;
      state.selected.clear();
      renderTools();
      renderHeadline();
      renderFields();
      renderFilm();
    };
  });
}

function renderHeadline() {
  const t = TOOLS.find((x) => x.id === state.tool);
  $("kicker").textContent = t.kicker;
  $("headline").textContent = t.headline;
  $("lede").textContent = t.lede;
}

function activeFile() {
  if (state.activeId) return state.files.find((f) => f.id === state.activeId) || state.files[0];
  return state.files[0];
}

function pw(fid) {
  return state.passwords[fid] || "";
}

function renderFolios() {
  const ul = $("folios");
  ul.innerHTML = state.files.map((f, i) => `
    <li class="folio" data-id="${f.id}">
      <span class="ord">${String(i + 1).padStart(2, "0")}</span>
      <div>
        <b>${escapeHtml(f.name)}</b>
        <span>${f.pages ? `${f.pages} pages · ` : ""}${fmtBytes(f.bytes)}${f.locked ? " · locked" : ""}</span>
      </div>
      ${f.locked ? `<input type="password" placeholder="Password" data-pw="${f.id}" value="${escapeAttr(pw(f.id))}" />` : `<span class="lock">${state.activeId === f.id ? "active" : "open"}</span>`}
      <button class="icon-btn" data-del="${f.id}" title="Remove">×</button>
    </li>`).join("");
  ul.querySelectorAll("[data-del]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/session/${state.sid}/files/${btn.dataset.del}`, { method: "DELETE" });
      state.files = state.files.filter((f) => f.id !== btn.dataset.del);
      if (state.activeId === btn.dataset.del) state.activeId = state.files[0]?.id || null;
      renderFolios();
      renderFilm();
    };
  });
  ul.querySelectorAll("[data-pw]").forEach((input) => {
    input.oninput = () => {
      state.passwords[input.dataset.pw] = input.value;
    };
    input.onchange = async () => {
      state.passwords[input.dataset.pw] = input.value;
      try {
        const item = await api(`/api/session/${state.sid}/files/${input.dataset.pw}/open`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password: input.value }),
        });
        const idx = state.files.findIndex((f) => f.id === item.id);
        if (idx >= 0) state.files[idx] = { ...state.files[idx], ...item };
        renderFolios();
        renderFilm();
      } catch (err) {
        showErr(err);
      }
    };
  });
  ul.querySelectorAll(".folio").forEach((row) => {
    row.onclick = (ev) => {
      if (ev.target.closest("button, input")) return;
      state.activeId = row.dataset.id;
      state.selected.clear();
      renderFolios();
      renderFilm();
    };
  });
}

function renderFields() {
  const box = $("fields");
  const tool = state.tool;
  const bits = [];
  if (tool === "split") {
    bits.push(`
      <label>How to cut</label>
      <select id="splitMode">
        <option value="split-range">Keep a page range (one PDF)</option>
        <option value="split-selected">Keep selected thumbnails</option>
        <option value="split-every">Split every N pages (zip)</option>
        <option value="split-all">One PDF per page (zip)</option>
      </select>
      <label>Page ranges</label>
      <input id="ranges" type="text" placeholder="1-3, 5, 8-10" />
      <label>Every N pages</label>
      <input id="every" type="number" min="1" value="1" />`);
  }
  if (tool === "rotate") {
    bits.push(`
      <label>Degrees</label>
      <select id="degrees">
        <option value="90">90° clockwise</option>
        <option value="180">180°</option>
        <option value="270">90° counter-clockwise</option>
      </select>`);
  }
  if (tool === "reorder") {
    bits.push(`
      <label>New order (every page once)</label>
      <input id="order" type="text" placeholder="3,1,2,4" />`);
  }
  if (tool === "compress") {
    bits.push(`
      <label>Size ceiling (optional)</label>
      <div class="pair">
        <input id="targetSize" type="number" min="0.1" step="0.1" placeholder="e.g. 2" />
        <select id="targetUnit">
          <option value="MB" selected>MB</option>
          <option value="KB">KB</option>
        </select>
      </div>`);
  }
  if (tool === "lock") {
    bits.push(`
      <label>New password</label>
      <input id="newPassword" type="password" autocomplete="new-password" />`);
  }
  if (tool === "watermark") {
    bits.push(`
      <label>Stamp text</label>
      <input id="watermark" type="text" placeholder="CONFIDENTIAL" />`);
  }
  if (tool === "meta") {
    bits.push(`
      <label>Title</label><input id="title" type="text" />
      <label>Author</label><input id="author" type="text" />
      <label>Subject</label><input id="subject" type="text" />
      <label>Keywords</label><input id="keywords" type="text" />`);
  }
  box.innerHTML = bits.join("") || `<p class="hint" style="min-height:0;margin:0">No extra knobs. Choose files, then run.</p>`;
  $("hint").textContent = hintFor(tool);
}

function hintFor(tool) {
  return {
    merge: "Files bind in the list order. Click × to drop one. Locked files need a password first.",
    split: "Ranges are 1-based. Selected thumbnails are used only in that mode.",
    unlock: "You must know the password. Bindery cannot crack unknown protection.",
    lock: "AES-256. Keep the password somewhere you already trust — not in this app.",
    rotate: "If nothing is selected, every page turns.",
    drop: "Select pages to remove in the filmstrip.",
    reorder: "Example: 3,1,2 rewrites a 3-page file.",
    compress: "Blank = lossless clean only. With a ceiling, photos are re-encoded from gentle to firmer until the copy fits. It will not drop below JPEG 70 / about 120 DPI.",
    watermark: "Visible overlay on every page of the copy.",
    text: "Downloads a .txt next to your other results.",
    images: "Downloads a zip of embedded bitmaps.",
    meta: "Empty fields are written as empty strings.",
  }[tool];
}

async function renderFilm() {
  const wrap = $("filmWrap");
  const file = activeFile();
  const needsFilm = ["split", "rotate", "drop", "reorder"].includes(state.tool);
  if (!needsFilm || !file || !file.pages) {
    wrap.hidden = true;
    return;
  }
  wrap.hidden = false;
  $("filmTitle").textContent = `${file.name} · ${file.pages} pages`;
  const thumbs = $("thumbs");
  thumbs.innerHTML = "";
  for (let i = 0; i < file.pages; i += 1) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `thumb${state.selected.has(i + 1) ? " selected" : ""}`;
    card.innerHTML = `<span class="n">${i + 1}</span><img alt="Page ${i + 1}" />`;
    const img = card.querySelector("img");
    const q = new URLSearchParams({ password: pw(file.id) });
    img.src = `/api/session/${state.sid}/files/${file.id}/thumb/${i}?${q}`;
    card.onclick = () => {
      if (state.selected.has(i + 1)) state.selected.delete(i + 1);
      else state.selected.add(i + 1);
      card.classList.toggle("selected");
    };
    thumbs.appendChild(card);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) {
  return escapeHtml(s);
}

async function ensureSession() {
  if (state.sid) return;
  const data = await api("/api/session", { method: "POST" });
  state.sid = data.id;
}

async function addFiles(fileList) {
  await ensureSession();
  const body = new FormData();
  [...fileList].forEach((f) => body.append("files", f));
  const data = await api(`/api/session/${state.sid}/files`, { method: "POST", body });
  state.files = data.all;
  if (!state.activeId && state.files[0]) state.activeId = state.files[0].id;
  renderFolios();
  renderFilm();
}

async function run() {
  const status = $("status");
  const dl = $("downloadBtn");
  status.hidden = false;
  dl.hidden = true;
  status.className = "status";
  status.textContent = "Working on this machine…";
  $("runBtn").disabled = true;
  try {
    await ensureSession();
    const file = activeFile();
    const tool = state.tool === "split" ? ($("splitMode")?.value || "split-range") : state.tool;
    const body = {
      tool,
      file_id: file?.id,
      file_ids: state.files.map((f) => f.id),
      passwords: state.passwords,
      password: file ? pw(file.id) : "",
      ranges: $("ranges")?.value || "",
      every: Number($("every")?.value || 1),
      degrees: Number($("degrees")?.value || 90),
      pages: [...state.selected],
      order: ($("order")?.value || "").split(/[,\s]+/).filter(Boolean).map(Number),
      new_password: $("newPassword")?.value || "",
      watermark: $("watermark")?.value || "",
      target_size: $("targetSize")?.value || "",
      target_unit: $("targetUnit")?.value || "MB",
      title: $("title")?.value || "",
      author: $("author")?.value || "",
      subject: $("subject")?.value || "",
      keywords: $("keywords")?.value || "",
    };
    const result = await api(`/api/session/${state.sid}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    let extra = "";
    if (result.bytes_before) extra = ` · ${fmtBytes(result.bytes_before)} → ${fmtBytes(result.bytes_after)}`;
    if (result.target_bytes) {
      extra += result.met_target
        ? ` · under ${fmtBytes(result.target_bytes)}`
        : ` · still over ${fmtBytes(result.target_bytes)}`;
    }
    if (result.jpeg_quality) extra += ` · JPEG ${result.jpeg_quality}${result.max_dpi ? ` / ${result.max_dpi} DPI` : ""}`;
    if (result.pages) extra = ` · ${result.pages} pages`;
    if (result.files) extra = ` · ${result.files} files in zip`;
    if (result.images) extra = ` · ${result.images} images`;
    status.textContent = `Ready: ${result.filename} (${fmtBytes(result.bytes)})${extra}`;
    if (result.note) status.textContent += ` ${result.note}`;
    if (result.met_target === false) status.className = "status warn";
    dl.hidden = false;
    dl.href = `/api/session/${state.sid}/download`;
    dl.download = result.filename;
    dl.textContent = `Download ${result.filename}`;
  } catch (err) {
    status.className = "status bad";
    status.textContent = err.message || String(err);
  } finally {
    $("runBtn").disabled = false;
  }
}

function wire() {
  const well = $("well");
  const input = $("fileInput");
  $("browseBtn").onclick = () => input.click();
  input.onchange = () => addFiles(input.files).catch(showErr);
  ["dragenter", "dragover"].forEach((ev) => {
    well.addEventListener(ev, (e) => { e.preventDefault(); well.classList.add("hot"); });
  });
  ["dragleave", "drop"].forEach((ev) => {
    well.addEventListener(ev, (e) => { e.preventDefault(); well.classList.remove("hot"); });
  });
  well.addEventListener("drop", (e) => addFiles(e.dataTransfer.files).catch(showErr));
  $("runBtn").onclick = () => run();
  $("selectAll").onclick = () => {
    const file = activeFile();
    if (!file?.pages) return;
    state.selected = new Set([...Array(file.pages)].map((_, i) => i + 1));
    renderFilm();
  };
  $("selectNone").onclick = () => { state.selected.clear(); renderFilm(); };
}

function showErr(err) {
  const status = $("status");
  status.hidden = false;
  status.className = "status bad";
  status.textContent = err.message || String(err);
}

renderTools();
renderHeadline();
renderFields();
wire();
ensureSession().catch(showErr);
api("/api/health").then((h) => {
  const pill = $("buildPill");
  const hint = $("runHint");
  if (h.packaged) {
    pill.textContent = "Packaged exe";
    hint.textContent = "This is a frozen copy. For live edits, close it and run run.bat instead.";
  } else if (h.app_window) {
    pill.textContent = "App window";
    hint.textContent = "Installed as a desktop app. Close the window to quit.";
  } else {
    pill.textContent = "From source";
    hint.textContent = "Live project files. Refresh the page after interface edits.";
  }
}).catch(() => {});
