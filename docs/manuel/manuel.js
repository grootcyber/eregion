/* The public manual (MAN1, #664). It reads modules.json (written from modules.yaml by
   `make manuel`), then GitHub's public API without a token: the open pull requests, the open
   issues and the last release. Without the API (offline, limited to 60 requests an hour, refused),
   the page shows what the repository says, and says so.
   Nothing read is ever written as HTML: every node is built by h(), its text by textContent, a link
   only from the repository's address and a number or a path checked here
   (tests/unit/test_manuel.py). */
"use strict";
(() => {
  const REPO = "https://github.com/grootcyber/eregion";
  const API = "https://api.github.com/repos/grootcyber/eregion";
  const ETATS = { prevue: "Prévue", dev: "En développement", relecture: "En relecture",
    main: "Sur main, pas encore publiée", livree: "Livrée" };
  const MOVING = ["dev", "relecture", "main"];
  const STEP_LABEL = { publiee: "publiée", montage: "en montage", prevue: "prévue" };
  // The public rule, the same as scripts/manuel.py: the YAML already holds a neutral name for these;
  // the page shows neither their lots, nor their issue, nor their pull request.
  const SENSIBLE = /(^|[^\w])(SEC-|V-\d|P-0)/i;
  const CACHE = "eregion-manuel-live-v1";
  const CACHE_MS = 10 * 60 * 1000;
  const TIMEOUT_MS = 8000;

  const state = { data: null, live: null, said: "", filtre: null };

  // ── building nodes, never HTML ──────────────────────────────────────────────────────
  const ATTRS = new Set(["type", "title", "id", "role", "rel", "target"]);
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "href") { if (isRepoUrl(v)) el.setAttribute("href", v); }
      else if (ATTRS.has(k) || k.startsWith("data-") || k.startsWith("aria-")) el.setAttribute(k, String(v));
    }
    for (const c of kids.flat()) {
      if (c === null || c === undefined || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  const $ = (id) => document.getElementById(id);
  const num = (n) => Number.isInteger(n) && n > 0;
  const safePath = (p) => typeof p === "string" && /^[A-Za-z0-9][\w./-]*$/.test(p) && !p.includes("..");
  const isRepoUrl = (u) => typeof u === "string" && (u === REPO || u.startsWith(REPO + "/"));
  const issueUrl = (n) => (num(n) ? `${REPO}/issues/${n}` : null);
  const pullUrl = (n) => (num(n) ? `${REPO}/pull/${n}` : null);
  const docUrl = (p) => (safePath(p) ? `${REPO}/blob/main/${p}` : null);
  const prsOf = (b) => (Array.isArray(b.pr) ? b.pr : [b.pr]).filter(num);
  const sensible = (b) => {
    const secu = new Set(Array.isArray(state.data.issues_securite) ? state.data.issues_securite : []);
    return SENSIBLE.test((Array.isArray(b.lots) ? b.lots : []).join(" ")) || b.securite === true
      || secu.has(b.issue) || prsOf(b).some((n) => secu.has(n));
  };
  // A version against the last release GitHub shows: "publiee", "a-publier" (the repository says it is
  // cut, GitHub has not published it yet), or "inconnu" (GitHub not read).
  const parts = (v) => String(v).split(".").map((x) => parseInt(x, 10) || 0);
  const newer = (a, b) => { const x = parts(a), y = parts(b); for (let i = 0; i < 3; i++) { if (x[i] !== y[i]) return x[i] > y[i]; } return false; };
  const pubState = (version) => {
    const latest = state.live && state.live.latest;
    if (!latest || !version) return "inconnu";
    return newer(version, latest.version) ? "a-publier" : "publiee";
  };
  const PUB_SAID = { publiee: "", "a-publier": ", à publier", inconnu: " (publication non vérifiée sur GitHub)" };
  const etatOf = (b) => (ETATS[b.shown] ? b.shown : "prevue");
  const pieceOf = (id) => (state.data.composants.find((c) => c.id === id) || { id, nom: id, role: "" });
  const posteOf = (id) => state.data.postes.find((p) => p.id === id);
  const hit = (b) => (state.filtre && b.release === state.filtre ? " hit" : "");

  // ── GitHub, read without a token ────────────────────────────────────────────────────
  async function getJSON(url) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), TIMEOUT_MS);
    try {
      const r = await fetch(url, { signal: ctl.signal, credentials: "omit", cache: "no-store" });
      if (!r.ok) {
        const e = new Error(`HTTP ${r.status}`);
        e.limited = r.status === 403 || r.status === 429;
        throw e;
      }
      return await r.json();
    } finally { clearTimeout(t); }
  }

  // Only what the page uses is kept, each value checked: numbers, a branch name, a tag, a date.
  function reduceLive(pulls, issues, releases) {
    const list = (x) => (Array.isArray(x) ? x : []);
    const open = list(pulls).filter((p) => p && num(p.number)).map((p) => ({
      number: p.number,
      head: typeof p?.head?.ref === "string" && /^[\w./-]{1,200}$/.test(p.head.ref) ? p.head.ref.toLowerCase() : "",
    }));
    const items = list(issues).filter((i) => i && num(i.number));
    const openIssues = items.filter((i) => !i.pull_request).map((i) => i.number);
    // The highest version published, not the last one created: a patch published on an older line
    // must not make a newer version read « à publier ».
    const rel = list(releases).filter((r) => r && !r.draft && !r.prerelease
      && typeof r.tag_name === "string" && /^v\d+\.\d+\.\d+$/.test(r.tag_name))
      .reduce((best, r) => (!best || newer(r.tag_name.slice(1), best.tag_name.slice(1)) ? r : best), null);
    const day = rel && typeof rel.published_at === "string" && /^\d{4}-\d{2}-\d{2}T/.test(rel.published_at)
      ? rel.published_at.slice(0, 10) : "";
    return { pulls: open, openIssues, complete: items.length < 100,
      latest: rel ? { version: rel.tag_name.slice(1), day } : null, at: Date.now() };
  }

  function cached() {
    try {
      const v = JSON.parse(sessionStorage.getItem(CACHE) || "null");
      if (v && Number.isFinite(v.at) && Date.now() - v.at < CACHE_MS && Array.isArray(v.pulls)) return v;
    } catch { /* no storage: read again */ }
    return null;
  }

  async function loadLive() {
    const hold = cached();
    if (hold) return hold;
    const [pulls, issues, releases] = await Promise.all([
      getJSON(`${API}/pulls?state=open&per_page=100`),
      getJSON(`${API}/issues?state=open&per_page=100`),
      getJSON(`${API}/releases?per_page=10`),
    ]);
    const live = reduceLive(pulls, issues, releases);
    try { sessionStorage.setItem(CACHE, JSON.stringify(live)); } catch { /* storage refused */ }
    return live;
  }

  const matchesLot = (head, lot) => {
    const l = "lot/" + String(lot).toLowerCase();
    return head === l || head.startsWith(l + "-");
  };

  // A brick as shown: the repository's state, with an open pull request on it read as « en
  // relecture » when the repository still says it is planned or in development.
  function shownBricks() {
    const live = state.live;
    const open = live ? new Set(live.openIssues) : null;
    return state.data.briques.map((b) => {
      const v = { ...b, shown: b.etat, livePr: null, issueState: "" };
      if (!live) return v;
      const lots = Array.isArray(b.lots) ? b.lots : [];
      const pr = live.pulls.find((p) => prsOf(b).includes(p.number) || (p.head && lots.some((l) => matchesLot(p.head, l))));
      if (pr) {
        v.livePr = pr.number;
        if (b.etat === "prevue" || b.etat === "dev") v.shown = "relecture";
      }
      if (num(b.issue)) v.issueState = open.has(b.issue) ? "ouverte" : live.complete ? "fermée" : "";
      return v;
    });
  }

  // ── rendering ───────────────────────────────────────────────────────────────────────
  const label = (b) => (etatOf(b) === "livree" ? `${ETATS.livree} en ${b.version}${PUB_SAID[pubState(b.version)]}`
    : ETATS[etatOf(b)]);
  function brick(b, extra = "") {
    return h("button", { type: "button", class: `brick ${etatOf(b)}${extra}`, "data-p": b.composant, "data-id": b.id,
      title: label(b) }, h("span", null, b.nom));
  }
  function mini(b) {
    const said = `${b.nom} · ${label(b)}`;
    return h("button", { type: "button", class: `mb ${etatOf(b)}${hit(b)}`, "data-p": b.composant, "data-id": b.id,
      title: said, "aria-label": said });
  }

  function renderTop(view) {
    const steps = state.data.releases;
    const pub = [...steps].reverse().find((s) => s.etat === "publiee");
    const mont = steps.find((s) => s.etat === "montage");
    const latest = state.live && state.live.latest;
    $("w-pub").textContent = latest ? latest.version : pub ? pub.derniere : "—";
    const ahead = latest && pub && newer(pub.derniere, latest.version) ? ` · ${pub.derniere} à publier` : "";
    $("w-pub-s").textContent = latest ? `sur GitHub${latest.day ? " · " + latest.day : ""}${ahead}`
      : pub ? `selon le dépôt, publication non vérifiée sur GitHub` : "";
    $("w-mont").textContent = mont ? mont.version : "—";
    $("w-mont-s").textContent = mont ? `« ${mont.nom} »` : "";
    const moving = view.filter((b) => MOVING.includes(b.shown));
    $("w-moving").textContent = `${moving.length} brique${moving.length > 1 ? "s" : ""}`;
    $("w-moving-s").textContent = "en développement, en relecture ou sur main";
    $("live").classList.toggle("off", !state.live);
    $("live-t").textContent = state.said;
  }

  function renderLegend() {
    $("legend-state").replaceChildren(...["livree", "main", "relecture", "dev", "prevue"].map((s) =>
      h("span", null, h("i", { class: `mb ${s}`, "data-p": "glorfindel", "aria-hidden": "true" }), ETATS[s].toLowerCase())));
  }

  function renderChips() {
    const opts = [{ v: null, l: "Tout" }, ...state.data.releases.map((r) => ({ v: r.version, l: r.version }))];
    $("chips").replaceChildren(...opts.map((o) => h("button", { type: "button", class: "chip",
      "data-v": o.v ?? "", "aria-pressed": String(state.filtre === o.v) }, o.l)));
  }

  function renderDiagram(view) {
    const groups = {};
    for (const b of view) {
      const p = posteOf(b.poste);
      (groups[p ? p.schema : b.composant] ||= []).push(b);
    }
    document.querySelectorAll("#dia-wrap .mbs[data-slot]").forEach((el) => {
      el.replaceChildren(...(groups[el.dataset.slot] || []).map(mini));
    });
    $("dia-wrap").classList.toggle("dim", !!state.filtre);
  }

  function renderBench(view) {
    $("bench").replaceChildren(...MOVING.map((s) => {
      const items = view.filter((b) => b.shown === s);
      const body = items.length ? items.map((b) => h("div", { class: "item" }, brick(b),
        h("span", { class: "sub mono" }, [pieceOf(b.composant).nom, b.release ? `release ${b.release}` : "",
          b.livePr ? (sensible(b) ? "PR ouverte" : `PR #${b.livePr} ouverte`) : ""].filter(Boolean).join(" · "))))
        : [h("span", { class: "empty" }, "Rien en ce moment.")];
      return h("div", { class: "col card" }, h("div", { class: "col-h" }, h("span", { class: "kicker" }, ETATS[s]),
        h("span", { class: "n" }, String(items.length))), body);
    }));
  }

  function renderPlan(view) {
    $("plan").classList.toggle("dim", !!state.filtre);
    $("plan").replaceChildren(...state.data.composants.map((c) => {
      const postes = state.data.postes.filter((p) => p.composant === c.id);
      const chains = [];
      for (const p of postes) {
        const label = p.chaine || "";
        if (!chains.length || chains[chains.length - 1].label !== label) chains.push({ label, postes: [] });
        chains[chains.length - 1].postes.push(p);
      }
      const flows = chains.map((ch) => {
        const stations = [];
        ch.postes.forEach((p, i) => {
          if (i) stations.push(h("span", { class: "link", "aria-hidden": "true" }, "→"));
          const items = view.filter((b) => b.poste === p.id);
          stations.push(h("div", { class: `station k-${p.nature}` }, h("h4", null, p.nom), h("small", null, p.legende),
            items.length ? items.map((b) => brick(b, hit(b))) : h("span", { class: "empty" }, "—")));
        });
        return h("div", null, ch.label ? h("span", { class: "flow-l" }, ch.label) : null, h("div", { class: "flow" }, stations));
      });
      const wide = chains.some((ch) => ch.postes.length > 3);
      return h("div", { class: `card${wide ? " wide" : ""}`, id: `piece-${c.id}` },
        h("div", { class: "xp-h" }, h("i", { "data-p": c.id }), h("h3", null, c.nom), h("p", null, c.role)),
        h("div", { class: "flows" }, flows));
    }));
  }

  function renderSteps(view) {
    const steps = state.data.releases;
    const stepLabel = (r, etat) => (etat !== "publiee" ? STEP_LABEL[etat]
      : { publiee: "publiée", "a-publier": "à publier", inconnu: "publiée selon le dépôt" }[pubState(r.derniere)]);
    $("tl").replaceChildren(...steps.map((r) => {
      const etat = STEP_LABEL[r.etat] ? r.etat : "prevue";
      return h("div", { class: `tn ${etat}${r.version === "1.0" ? " diamond" : ""}` },
        etat === "montage" ? h("span", { class: "here" }, "on est ici") : null,
        h("span", { class: "v" }, r.version), h("i", { class: "dot" }), h("b", null, r.nom),
        h("small", null, r.derniere ? `${r.derniere}${r.date ? " · " + r.date : ""}` : ""));
    }));
    $("steps").replaceChildren(...steps.map((r, i) => {
      const etat = STEP_LABEL[r.etat] ? r.etat : "prevue";
      const parts = view.filter((b) => b.release === r.version);
      return h("li", { class: `step ${etat}` }, h("span", { class: "num" }, String(i + 1)),
        h("div", { class: "step-body" },
          h("div", { class: "step-t" }, h("span", { class: "v" }, r.version), h("h3", null, r.nom),
            h("span", { class: `pill ${etat}` }, stepLabel(r, etat)),
            r.derniere ? h("span", { class: "mono" }, `dernière : ${r.derniere}${r.date ? " · " + r.date : ""}`) : null),
          r.resume ? h("p", null, r.resume) : null,
          h("div", { class: "parts" }, parts.map((b) => brick(b)))));
    }));
  }

  function openSheet(id) {
    const b = shownBricks().find((x) => x.id === id);
    if (!b) return;
    const piece = pieceOf(b.composant);
    const poste = posteOf(b.poste);
    const links = [];
    const a = (href, text) => h("a", { href, target: "_blank", rel: "noopener" }, text);
    const secret = sensible(b);
    const prs = [...new Set([b.livePr, ...prsOf(b)].filter(num))];
    if (!secret) {
      for (const n of prs) links.push(a(pullUrl(n), `PR #${n}`));
      if (issueUrl(b.issue)) links.push(a(issueUrl(b.issue), `issue #${b.issue}${b.issueState ? " (" + b.issueState + ")" : ""}`));
    }
    const doc = docUrl(b.doc) ? b.doc : docUrl(piece.doc) ? piece.doc : null;
    if (doc) links.push(a(docUrl(doc), doc));
    const row = (dt, dd, cls) => (dd ? [h("dt", null, dt), h("dd", cls ? { class: cls } : null, dd)] : []);
    const lots = !secret && Array.isArray(b.lots) && b.lots.length ? b.lots.join(", ") : "";
    const said = b.shown !== b.etat ? `${ETATS[etatOf(b)]} (une pull request ouverte sur GitHub)`
      : b.etat === "livree" ? `${ETATS.livree} en ${b.version}${PUB_SAID[pubState(b.version)]}` : ETATS[etatOf(b)];
    const close = h("button", { type: "button", class: "close", id: "s-close" }, "Fermer");
    $("sheet-body").replaceChildren(
      h("div", { class: "sheet-h" }, h("div", null, h("span", { class: "kicker" }, piece.nom),
        h("h2", { id: "s-title" }, b.nom)), close),
      h("div", null, brick(b)),
      h("dl", null,
        row("État", said),
        row("Release", b.release),
        row("Étape", poste ? `${poste.nom} — ${poste.legende}` : ""),
        row("Lots", lots, "mono"),
        row("Note", b.etat === "livree" && !secret ? b.note : ""),
        links.length ? [h("dt", null, "Liens"), h("dd", null, links.flatMap((l, i) => (i ? [" · ", l] : [l])))] : []));
    const dlg = $("sheet");
    close.addEventListener("click", () => dlg.close());
    try { dlg.showModal(); } catch { dlg.setAttribute("open", ""); }
  }

  function renderAll() {
    const view = shownBricks();
    renderTop(view); renderDiagram(view); renderBench(view); renderChips(); renderPlan(view); renderSteps(view);
  }

  document.addEventListener("click", (e) => {
    const t = e.target instanceof Element ? e.target : null;
    if (!t) return;
    const br = t.closest("button.brick, button.mb");
    if (br && br.dataset.id && state.data) { openSheet(br.dataset.id); return; }
    const ch = t.closest("#chips button.chip");
    if (ch && state.data) { state.filtre = ch.dataset.v || null; renderAll(); }
  });
  $("sheet").addEventListener("click", (e) => { if (e.target === $("sheet")) $("sheet").close(); });

  function valid(d) {
    return d && ["composants", "postes", "releases", "briques"].every((k) => Array.isArray(d[k]));
  }

  async function start() {
    renderLegend();
    try {
      const r = await fetch("modules.json", { cache: "no-cache" });
      const d = await r.json();
      if (!r.ok || !valid(d)) throw new Error("modules.json");
      state.data = d;
    } catch {
      $("live-t").textContent = "le manuel ne se lit pas";
      $("bench").replaceChildren(h("div", { class: "state-msg" },
        "modules.json ne se lit pas ici. Ouvre la page sur le site du projet, ou lis le manuel dans le dépôt : ",
        h("a", { href: `${REPO}/blob/main/docs/manuel/modules.yaml` }, "docs/manuel/modules.yaml"), "."));
      return;
    }
    state.said = "l'état écrit dans le dépôt · lecture de GitHub…";
    renderAll();
    try {
      state.live = await loadLive();
      const at = new Date(state.live.at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
      state.said = `l'état du dépôt, et GitHub lu à ${at}`;
    } catch (e) {
      state.live = null;
      state.said = e && e.limited
        ? "limite de l'API de GitHub atteinte : l'état écrit dans le dépôt"
        : "GitHub ne répond pas : l'état écrit dans le dépôt";
    }
    renderAll();
  }
  start();
})();
