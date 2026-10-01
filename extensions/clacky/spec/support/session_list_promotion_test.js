"use strict";

// Regression harness for sidebar promotions driven by `session_update`.
//
// Sessions opened from search results / deep links live only in Sessions'
// `_extraSessions` cache, which the sidebar never renders. When the user works
// on such a session (sends a message → the backend broadcasts a full
// `session_update` snapshot), it must be promoted into the canonical list and
// drawn in the sidebar — otherwise nothing shows up until a page reload.
//
// The real sessions.js + ws-dispatcher.js run against a minimal DOM stub, so
// the assertions cover the user-visible outcome: which rows the sidebar holds.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = name => path.resolve(__dirname, "../../lib/clacky/web", name);

// Unknown module methods are auto-stubbed: this harness only cares about the
// session list, so the chat panel / composer side effects are irrelevant.
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
  // renderList() clears the container by assigning innerHTML = "".
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

function boot() {
  const nodes = {};
  // Timers created by the modules under test (e.g. the transient "done" dot)
  // must not keep the process alive after the assertions finish.
  const unrefTimeout = (fn, ms, ...args) => {
    const timer = setTimeout(fn, ms, ...args);
    if (timer.unref) timer.unref();
    return timer;
  };
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
    setTimeout: unrefTimeout,
    clearTimeout,
    document,
    fetch: async () => ({ ok: false, json: async () => ({}) }),
    I18n: { t: key => key, lang: () => "en" },
    WS: {
      onEvent: fn => { context.__dispatcher = fn; },
      setSubscribedSession() {},
      send() {},
    },
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
  vm.runInContext(fs.readFileSync(sourcePath("ws-dispatcher.js"), "utf8"), context);

  const Sessions = vm.runInContext("Clacky.Sessions", context);
  const list = document.getElementById("session-list");
  return { Sessions, list, dispatch: context.__dispatcher };
}

const row = (id, extra = {}) => Object.assign({
  id, name: id, status: "idle", source: "manual",
  created_at: "2026-08-01T00:00:00+08:00",
  updated_at: "2026-08-01T00:00:00+08:00",
}, extra);

// Sidebar row ids, top to bottom.
const renderedIds = list => list.children.map(child => child.dataset.sessionId);

function tests() {
  // 1. The reported bug: an old session found via search (outside the loaded
  //    page, absent from the sidebar) receives its first activity snapshot →
  //    it must show up in the list, sorted where its fresh updated_at puts it.
  {
    const { Sessions, list, dispatch } = boot();
    Sessions.setAll([row("page-1"), row("page-2")]);
    Sessions._setActiveId("old-1");
    Sessions.renderList();
    assert.deepEqual(renderedIds(list), ["page-1", "page-2"], "old session is not listed yet");

    dispatch({
      type: "session_update",
      session: row("old-1", { status: "running", updated_at: "2026-09-15T16:00:00+08:00" }),
    });

    assert.deepEqual(renderedIds(list), ["old-1", "page-1", "page-2"],
      "the session the user just messaged appears at the top of the sidebar");
  }

  // 2. Sessions the user is NOT looking at must stay out of the paginated
  //    list — pulling them in would corrupt the loadMore cursor.
  {
    const { Sessions, list, dispatch } = boot();
    Sessions.setAll([row("page-1")]);
    Sessions._setActiveId("page-1");
    Sessions.renderList();

    dispatch({ type: "session_update", session: row("background-1", { status: "running" }) });

    assert.deepEqual(renderedIds(list), ["page-1"],
      "a background session is not inserted into the sidebar list");
    assert.equal(Sessions.all.some(s => s.id === "background-1"), false);
  }

  // 3. Creation updates keep promoting the row.
  {
    const { Sessions, list, dispatch } = boot();
    Sessions.setAll([row("page-1")]);
    Sessions.renderList();

    dispatch({
      type: "session_update", created: true,
      session: row("new-1", { updated_at: "2026-09-15T16:00:00+08:00" }),
    });

    assert.deepEqual(renderedIds(list), ["new-1", "page-1"]);
  }

  // 4. An already-listed session is patched in place — no duplicate row.
  {
    const { Sessions, list, dispatch } = boot();
    Sessions.setAll([row("page-1")]);
    Sessions._setActiveId("page-1");
    Sessions.renderList();

    dispatch({ type: "session_update", session: row("page-1", { status: "running" }) });

    assert.deepEqual(renderedIds(list), ["page-1"], "no duplicate row");
  }
}

tests();
console.log("session_list_promotion_test: ok");
