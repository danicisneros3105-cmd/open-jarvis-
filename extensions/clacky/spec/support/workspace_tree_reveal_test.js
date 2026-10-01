"use strict";

// Regression harness for revealing a chat-linked file in the tree.
//
// The tree loads one level at a time, so a file living in a subfolder had no
// row to highlight: opening it from a chat link left the user staring at a
// collapsed parent with no idea where the file was. Clicking such a link must
// expand each parent folder on the way down and mark the file's row.
//
// The real view.js runs against a DOM stub that implements enough of the
// element API (class/attribute selectors) for the tree code to walk itself.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = name => path.resolve(__dirname, "../../lib/clacky/web", name);

function parseSelector(selector) {
  const attrs = [];
  const rest = selector.replace(/\[([\w-]+)="([^"]*)"\]/g, (_m, key, value) => {
    attrs.push([key, value]);
    return "";
  });
  const classes = rest.split(".").slice(1).map(s => s.trim()).filter(Boolean);
  const tag = rest.startsWith(".") ? null : (rest.split(".")[0].trim() || null);
  return { tag, classes, attrs };
}

function matches(el, selector) {
  const sel = parseSelector(selector);
  if (sel.tag && el.tagName !== sel.tag) return false;
  const classes = (el.className || "").split(/\s+/).filter(Boolean);
  if (!sel.classes.every(c => classes.includes(c))) return false;
  return sel.attrs.every(([key, value]) => {
    if (key.startsWith("data-")) {
      const prop = key.slice(5).replace(/-([a-z])/g, (_m, ch) => ch.toUpperCase());
      return el.dataset[prop] === value;
    }
    return el.attrs[key] === value;
  });
}

function descendants(root) {
  const out = [];
  for (const child of root.children || []) {
    out.push(child, ...descendants(child));
  }
  return out;
}

class Element {
  constructor(tag = "div") {
    this.tagName = tag;
    this.style = { setProperty() {} };
    this.dataset = {};
    this.attrs = {};
    this.children = [];
    this.handlers = {};
    this.classes = new Set();
    this._className = "";
    this._innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.classList = {
      add: n => this.classes.add(n),
      remove: n => this.classes.delete(n),
      toggle: (n, on) => (on ? this.classes.add(n) : this.classes.delete(n)),
      contains: n => this.classes.has(n),
    };
  }
  set className(v) { this._className = v; this.classes = new Set(v.split(/\s+/).filter(Boolean)); }
  get className() { return this._className; }
  get parentElement() { return this.parentNode || null; }
  set innerHTML(v) { this._innerHTML = v; if (v === "") this.children = []; }
  get innerHTML() { return this._innerHTML; }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return this.attrs[k]; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(k, fn) { this.handlers[k] = fn; }
  removeEventListener() {}
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  append(...kids) { kids.forEach(k => this.appendChild(k)); }
  prepend(child) { this.children.unshift(child); return child; }
  insertBefore(child) { this.children.unshift(child); return child; }
  replaceChildren(...kids) { this.children = kids; }
  remove() {}
  querySelector(selector) { return descendants(this).find(el => matches(el, selector)) || null; }
  querySelectorAll(selector) { return descendants(this).filter(el => matches(el, selector)); }
  getBoundingClientRect() { return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 }; }
  contains() { return false; }
  closest() { return null; }
  scrollIntoView() {}
  focus() {}
  click() { const fn = this.handlers.click; if (fn) fn({ preventDefault() {}, stopPropagation() {} }); }
}

function findByClass(root, cls) {
  if ((root.className || "").split(/\s+/).includes(cls)) return root;
  for (const child of root.children || []) {
    const hit = findByClass(child, cls);
    if (hit) return hit;
  }
  return null;
}

const TREE = {
  "": [
    { name: "Word示例", path: "Word示例", type: "dir" },
    { name: "report.docx", path: "report.docx", type: "file", size: 1 },
    { name: "index.html", path: "index.html", type: "file", size: 12 },
  ],
  "Word示例": [
    { name: "子目录", path: "Word示例/子目录", type: "dir" },
    { name: "Word示例文档.docx", path: "Word示例/Word示例文档.docx", type: "file", size: 47000 },
  ],
  "Word示例/子目录": [
    { name: "deep.docx", path: "Word示例/子目录/deep.docx", type: "file", size: 1 },
  ],
};

// `treeDelay` holds the root listing back so a link can be clicked while the
// tree is still loading.
function boot(opts = {}) {
  const fetches = [];
  const nodes = {};

  const document = {
    createElement: tag => new Element(tag),
    createDocumentFragment: () => new Element("fragment"),
    getElementById: id => nodes[id] || (nodes[id] = new Element()),
    addEventListener() {},
    querySelector: () => null,
    querySelectorAll: () => [],
    body: new Element("body"),
  };

  const context = {
    console, Date, Map, Set, Math, JSON, Promise, URL, URLSearchParams,
    setTimeout, clearTimeout, requestAnimationFrame: fn => setTimeout(fn, 0),
    CSS: { escape: s => String(s) },
    navigator: { platform: "MacIntel", clipboard: { writeText: async () => {} } },
    document,
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    I18n: { t: key => key, lang: () => "en" },
    Modal: { toast() {} },
    Clacky: { ext: { emit() {}, ui: { mountBuiltin() {} } } },
    fetch: async (url, options) => {
      fetches.push({ url: String(url), options });
      if (String(url).includes("/files")) {
        const rel = new URL(String(url), "http://localhost").searchParams.get("path") || "";
        if (opts.treeDelay) await new Promise(r => setTimeout(r, opts.treeDelay));
        return { ok: true, status: 200, json: async () => ({ root: "/wd", entries: TREE[rel] || [] }) };
      }
      return { ok: true, status: 200, json: async () => ({ ok: true }) };
    },
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);

  ["features/workspace/store.js", "components/code-editor.js", "features/workspace/view.js"]
    .forEach(file => vm.runInContext(fs.readFileSync(sourcePath(file), "utf8"), context));

  const WorkspaceView = vm.runInContext("Clacky.WorkspaceView", context);
  const Workspace = vm.runInContext("Clacky.Workspace", context);
  Workspace.setSession({ id: "s1", working_dir: "/wd" });

  const container = new Element("div");
  WorkspaceView.mount(container, {});

  return { WorkspaceView, container, fetches };
}

async function settle(times = 3) {
  for (let i = 0; i < times; i++) await new Promise(resolve => setTimeout(resolve, 0));
}

const dirLoads = (w, rel) => w.fetches.filter(f => {
  if (!f.url.includes("/files")) return false;
  return new URL(f.url, "http://localhost").searchParams.get("path") === rel;
});

const fileRow = (w, relPath) => findByClass(w.container, "wt-tree")
  .querySelector(`.wt-row[data-path="${relPath}"]`);

async function tests() {
  // 1. A file in a subfolder: the folder expands and the file ends up selected.
  {
    const w = boot();
    await settle();
    w.WorkspaceView.openFile("/wd/Word示例/Word示例文档.docx");
    await settle();

    const dirRow = fileRow(w, "Word示例");
    assert.ok(dirRow.querySelector(".wt-caret").classList.contains("open"),
      "the parent folder is expanded");
    assert.equal(dirLoads(w, "Word示例").length, 1, "its contents were fetched once");

    const row = fileRow(w, "Word示例/Word示例文档.docx");
    assert.ok(row, "the file has a row in the tree");
    assert.ok(row.classList.contains("active"), "the file row is selected");
  }

  // 2. Nested subfolders expand all the way down.
  {
    const w = boot();
    await settle();
    w.WorkspaceView.openFile("/wd/Word示例/子目录/deep.docx");
    await settle();

    assert.equal(dirLoads(w, "Word示例").length, 1, "the first level was fetched");
    assert.equal(dirLoads(w, "Word示例/子目录").length, 1, "the second level was fetched");
    assert.ok(fileRow(w, "Word示例/子目录/deep.docx").classList.contains("active"),
      "the nested file is selected");
  }

  // 3. A file in the working dir itself needs no expansion.
  {
    const w = boot();
    await settle();
    w.WorkspaceView.openFile("/wd/report.docx");
    await settle();

    assert.equal(w.fetches.filter(f => f.url.includes("/files")).length, 1,
      "only the root listing was fetched");
    assert.ok(fileRow(w, "report.docx").classList.contains("active"),
      "the root-level file is selected");
  }

  // 4. A link clicked while the tree is still loading waits it out.
  {
    const w = boot({ treeDelay: 20 });
    w.WorkspaceView.openFile("/wd/Word示例/Word示例文档.docx");
    await new Promise(resolve => setTimeout(resolve, 80));
    await settle();

    assert.ok(fileRow(w, "Word示例/Word示例文档.docx").classList.contains("active"),
      "the file is selected once the tree arrives");
  }

  // 5. Re-opening the same file does not re-fetch an already expanded folder.
  {
    const w = boot();
    await settle();
    w.WorkspaceView.openFile("/wd/Word示例/Word示例文档.docx");
    await settle();
    w.WorkspaceView.openFile("/wd/Word示例/Word示例文档.docx");
    await settle();

    assert.equal(dirLoads(w, "Word示例").length, 1, "the folder is not reloaded");
  }

  // 6. A path outside the working dir has no row and must not break the tree.
  {
    const w = boot();
    await settle();
    w.WorkspaceView.openFile("/tmp/elsewhere/report.docx");
    await settle();

    assert.equal(w.fetches.filter(f => f.url.includes("/files")).length, 1,
      "no directory fetches are attempted");
    assert.equal(fileRow(w, "index.html").classList.contains("active"), false,
      "nothing else gets selected");
  }
}

tests().then(
  () => console.log("workspace_tree_reveal_test: ok"),
  err => { console.error(err); process.exit(1); }
);
