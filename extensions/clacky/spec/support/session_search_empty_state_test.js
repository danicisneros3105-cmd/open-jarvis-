"use strict";

// Regression harness for the search overlay's empty state.
//
// A query that matches nothing used to print the "no content matches" line
// twice: once by the content section (which always renders its own empty
// placeholder) and again by the overall fallback. The real sessions.js runs
// against a minimal DOM stub, so the assertion counts the placeholder nodes
// the user actually sees.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = name => path.resolve(__dirname, "../../lib/clacky/web", name);

const autoStub = (extra = {}) => new Proxy(extra, {
  get: (target, key) => (key in target ? target[key] : () => {}),
});

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
    this.value = "";
    this.textContent = "";
    this.classList = {
      add: n => this.classes.add(n),
      remove: n => this.classes.delete(n),
      toggle: (n, on) => (on ? this.classes.add(n) : this.classes.delete(n)),
      contains: n => this.classes.has(n),
    };
  }
  set className(v) { this._className = v; this.classes = new Set(v.split(/\s+/).filter(Boolean)); }
  get className() { return this._className; }
  set innerHTML(v) { this._innerHTML = v; if (v === "") this.children = []; }
  get innerHTML() { return this._innerHTML; }
  setAttribute(k, v) { this.attrs[k] = v; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(k, fn) { this.handlers[k] = fn; }
  removeEventListener() {}
  appendChild(child) { this.children.push(child); child.parentNode = this; return child; }
  append(...kids) { kids.forEach(k => this.appendChild(k)); }
  prepend(child) { this.children.unshift(child); return child; }
  remove() {}
  replaceChildren(...kids) { this.children = kids; }
  insertBefore(child) { this.children.unshift(child); return child; }
  querySelector() { return new Element(); }
  querySelectorAll() { return []; }
  getBoundingClientRect() { return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 }; }
  contains() { return false; }
  closest() { return null; }
  focus() {}
}

// `responses` maps a q_scope ("name" | "content") to the payload the API
// should answer with; `null` makes that request fail.
function boot(responses) {
  const nodes = {};
  const document = {
    createElement: tag => new Element(tag),
    createDocumentFragment: () => new Element("fragment"),
    getElementById: id => nodes[id] || (nodes[id] = new Element()),
    addEventListener() {},
    querySelector: () => null,
    querySelectorAll: () => [],
    body: new Element(),
  };

  const context = {
    console, Date, Map, Set, Math, JSON, Promise, URLSearchParams,
    setTimeout, clearTimeout,
    document,
    fetch: async url => {
      const scope = new URL(url, "http://localhost").searchParams.get("q_scope");
      const payload = responses[scope];
      if (!payload) return { ok: false, json: async () => ({}) };
      return { ok: true, json: async () => payload };
    },
    I18n: { t: key => key, lang: () => "en" },
    WS: { onEvent() {}, setSubscribedSession() {}, send() {} },
    Clacky: {},
    $: id => document.getElementById(id),
    escapeHtml: s => String(s === undefined || s === null ? "" : s),
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    Router: autoStub(),
    Projects: autoStub(),
    Tasks: autoStub(),
    Skills: autoStub(),
    Composer: autoStub({ text: () => "", chips: () => [] }),
    IME: autoStub({ track: () => ({ isComposing: () => false, dispose() {} }) }),
    alert() {},
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);

  vm.runInContext(fs.readFileSync(sourcePath("utils.js"), "utf8"), context);
  vm.runInContext(fs.readFileSync(sourcePath("sessions.js"), "utf8"), context);

  const Sessions = vm.runInContext("Clacky.Sessions", context);
  const results = document.getElementById("session-search-results");
  return { Sessions, document, results };
}

// Search for `q` and return the placeholder / header nodes the overlay holds.
async function search(responses, q) {
  const { Sessions, document, results } = boot(responses);
  document.getElementById("session-search-q").value = q;
  await Sessions.commitSearch();
  const byClass = cls => results.children.filter(c => c.className === cls);
  return {
    results,
    headers:    byClass("session-search-group").map(c => c.textContent),
    emptyTexts: byClass("session-empty").map(c => c.textContent),
    rows:       results.children.filter(c => c.dataset.sessionId),
  };
}

const session = (id, extra = {}) => Object.assign({
  id, name: id, status: "idle", source: "manual",
  created_at: "2026-08-01T00:00:00+08:00",
  updated_at: "2026-08-01T00:00:00+08:00",
}, extra);

const empty = { sessions: [] };

async function tests() {
  // 1. The reported bug: a query matching nothing showed the message twice.
  {
    const { headers, emptyTexts } = await search({ name: empty, content: empty }, "吃");

    assert.deepEqual(emptyTexts, ["sessions.search.contentEmpty"],
      "the empty placeholder is rendered exactly once");
    assert.deepEqual(headers, ["sessions.search.byContent"],
      "the content section header still shows the 0 count");
  }

  // 2. No content-search result at all (request failed) still explains itself once.
  {
    const { emptyTexts } = await search({ name: empty, content: null }, "吃");

    assert.deepEqual(emptyTexts, ["sessions.search.contentEmpty"],
      "a failed content search keeps a single placeholder");
  }

  // 3. When the query does match content, the placeholder is gone.
  {
    const { emptyTexts, rows } = await search({
      name: empty,
      content: { sessions: [session("hit-1", { search_snippet: "...吃..." })] },
    }, "吃");

    assert.deepEqual(emptyTexts, [], "no placeholder when there is a match");
    assert.equal(rows.length, 1, "the matching session is listed");
  }

  // 4. Name matches alone do not add a second placeholder.
  {
    const { emptyTexts, rows } = await search({
      name:        { sessions: [session("named-1")] },
      content:     empty,
    }, "吃");

    assert.deepEqual(emptyTexts, ["sessions.search.contentEmpty"],
      "only the content section reports its own emptiness");
    assert.equal(rows.length, 1);
  }
}

tests().then(
  () => console.log("session_search_empty_state_test: ok"),
  err => { console.error(err); process.exit(1); }
);
