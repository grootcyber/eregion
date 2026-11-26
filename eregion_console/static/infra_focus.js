// FOC1 (#1231; Jonathan 26/11, on a mockup): the focus in the infrastructure map. A tile hovered, or given the
// keyboard's focus, stays sharp and its lines come to the front; the other tiles and lines step back. A backend
// hovered (a log source, the network control, a vault): its lines and the tiles they reach come to the front. A
// delay of about 120 ms, so that the map never flickers from one tile to the next; no focus while a tile is
// dragged, while a window is open, or on a phone (no lines there). Pure — no page, no timer of its own: what
// glorfindel.js applies is decided here, and the suite runs it as it is (tests/unit/test_console_focus.py).
//
// A focus: { tile: <a tile's key> } or { backend: <a backend node's id: nb-<name>, module-protect> } or null.
// A line, as the map draws it: { k: <the key of the tile it reaches, or ''>, b: <the id of the node it leaves> }.
const InfraFocus = (() => {
  const DELAY = 120;

  // What a focus lights: a tile — itself, the lines that reach it and the nodes they leave; a backend — itself,
  // its lines, and the tiles they reach. Null: nothing focused, nothing steps back.
  function lit(focus, lines) {
    if (!focus || !(focus.tile || focus.backend)) return null;
    const on = new Set(), tiles = new Set(), nodes = new Set();
    lines.forEach((l, i) => {
      if (focus.tile ? l.k === focus.tile : l.b === focus.backend) {
        on.add(i);
        if (l.k) tiles.add(l.k);
        if (l.b) nodes.add(l.b);
      }
    });
    if (focus.tile) tiles.add(focus.tile);
    if (focus.backend) nodes.add(focus.backend);
    return { lines: on, tiles, nodes };
  }

  // No focus while a tile is dragged, a window is open, or on a phone.
  function allowed(env) { return !env.dragging && !env.modal && !env.phone; }

  // The delay: a focus wanted is applied after DELAY, unless another is wanted before — the last one wins, and
  // a move from one tile to the next never passes through « nothing ». The page gives the timer.
  function scheduler(later, cancel, apply) {
    let timer = null, current = null;
    const same = (a, b) => JSON.stringify(a || null) === JSON.stringify(b || null);
    return {
      want(focus) {
        if (timer !== null) { cancel(timer); timer = null; }
        if (same(focus, current)) return;
        timer = later(() => { timer = null; current = focus || null; apply(current); }, DELAY);
      },
      // At once, without the delay: a drag starts, a window opens.
      now(focus) {
        if (timer !== null) { cancel(timer); timer = null; }
        current = focus || null;
        apply(current);
      },
      current: () => current,
    };
  }

  return { DELAY, lit, allowed, scheduler };
})();
