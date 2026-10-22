/* Trails. The drawing on the page carries on down it: long tentacles hang from the rim of the
   jellyfish's bell and run down the margin beside the text; each section's rule is one of them
   peeling off in a curl. Past the last rule the long ones run on, thinning out and fading to
   nothing a little above the foot of the page; the rest fade out partway. None crosses text.
   Everything is measured and drawn into ONE SVG overlay under the text. Without JS the plain CSS
   hairlines stay (they are hidden only under html.has-trails). A page without sections is left
   alone. */
(function () {
  var doc = document, root = doc.documentElement, page = doc.querySelector(".page");
  if (!page || !doc.querySelector(".sec") || !window.ResizeObserver) return;
  var NS = "http://www.w3.org/2000/svg", svg = doc.createElementNS(NS, "svg");
  svg.setAttribute("class", "trails");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  page.insertBefore(svg, page.firstChild);

  var phone = matchMedia("(max-width: 47.5em)"), still = matchMedia("(prefers-reduced-motion: reduce)");
  var ready = false, queued = false, firstDraw = true, drawn = "", PI = Math.PI,
      SPEED = .8,               // draw-in: px of tentacle per ms
      FADE = 12;                // a long tentacle fades out over its last FADE rem
  // Points on the right half of the bell rim where the long tentacles start (fractions of the
  // drawing's box; the oral arms hang from the centre), and on the left half (RIML, the mirror
  // images of the outer three about the bell's axis, which is at x = .556 of the box).
  var RIM = [.61, .494, .71, .482, .82, .448, .90, .406],
      RIML = [.211, .406, .291, .448, .401, .482];

  function rnd(a) {             // mulberry32: the same numbers on every load
    return function () {
      a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function n(v) { return Math.round(v * 100) / 100; }
  function poly(P) {            // polyline [x0,y0, x1,y1, ...] as path data
    for (var s = "", i = 0; i < P.length; i += 2) s += (i ? "L" : "M") + n(P[i]) + " " + n(P[i + 1]);
    return s;
  }
  function cumul(P) {           // arc length at every point of P
    for (var c = [0], i = 2; i < P.length; i += 2) c.push(c[c.length - 1] + Math.hypot(P[i] - P[i - 2], P[i + 1] - P[i - 1]));
    return c;
  }
  function ribbon(P, wf) {      // outline around polyline P, wf(u) wide at arc-length fraction u
    var L = [], R = [], m = P.length, c = cumul(P), tot = c[c.length - 1] || 1;
    for (var i = 0; i < m; i += 2) {
      var a = Math.max(i - 2, 0), b = Math.min(i + 2, m - 2),
          dx = P[b] - P[a], dy = P[b + 1] - P[a + 1], d = Math.hypot(dx, dy) || 1,
          w = wf(c[i / 2] / tot, c[i / 2]) / 2, nx = -dy / d * w, ny = dx / d * w;
      L.push(n(P[i] + nx) + " " + n(P[i + 1] + ny));
      R.unshift(n(P[i] - nx) + " " + n(P[i + 1] - ny));
    }
    return "M" + L.join("L") + "L" + R.join("L") + "Z";
  }
  // A curl: starts heading th and turns `turns` times (dir 1 = clockwise on screen) with radius
  // rf(u) at turned fraction u. `ease` lets it leave its parent gently and straighten at the end.
  function coil(th, turns, rf, dir, ease) {
    var P = [0, 0], x = 0, y = 0, a = 0, A = turns * 2 * PI;
    for (var guard = 0; a < A && guard < 6000; guard++) {
      var u = a / A, r = rf(u),
          k = ease ? Math.min(1, .22 + .78 * u / .14, .3 + .7 * (1 - u) / .12) : Math.min(1, .3 + .7 * u / .1),
          ds = .6, da = Math.min(ds * k / r, A - a);
      a += da;
      var h = th + dir * a;
      x += Math.cos(h) * ds; y += Math.sin(h) * ds;
      P.push(x, y);
    }
    return { P: P, end: [x, y], h: th + dir * A };
  }
  function tear(r0, rm, r1, um) {   // wide sweep in, a small loop at um, opening out again
    return function (u) { return u < um ? rm + (r0 - rm) * Math.pow((um - u) / um, 1.3) : rm + (r1 - rm) * Math.pow((u - um) / (1 - um), 1.3); };
  }
  function shift(P, x, y) { for (var Q = [], i = 0; i < P.length; i += 2) Q.push(P[i] + x, P[i + 1] + y); return Q; }

  function draw() {
    if (!queued) return;
    queued = false;
    if (!ready) return;
    try { render(); } catch (e) { root.classList.remove("has-trails"); svg.innerHTML = ""; throw e; }
  }

  function render() {
    var P = page.getBoundingClientRect(), W = P.width, H = P.height, cs = getComputedStyle(root),
        small = phone.matches, rem = parseFloat(cs.fontSize) || 16,
        anim = firstDraw && !still.matches && doc.visibilityState == "visible";
    function box(el) {          // an element's box, relative to the page
      var r = el.getBoundingClientRect();
      return { l: r.left - P.left, t: r.top - P.top, r: r.right - P.left, b: r.bottom - P.top, w: r.width, h: r.height };
    }
    function bottom(el) { return Math.max.apply(null, [].map.call(el.children, function (c) { return box(c).b; })); }
    drawn = W + "x" + H;
    firstDraw = false;

    // 1. The rules: the top edge of every section (as wide as the section). The text above the
    //    first one is the lede.
    var rules = [], colR = 0, secs = doc.querySelectorAll(".sec"), le = doc.querySelector(".lede-col"), lede = le && box(le);
    [].forEach.call(secs, function (s, i) {
      var b = box(s);
      colR = Math.max(colR, b.r);
      rules.push({ id: s.id || String(i), y: Math.round(b.t) + .5, l: b.l, r: b.r,
                   above: i ? bottom(secs[i - 1]) : lede ? lede.b : b.t });
    });
    if (lede) colR = Math.max(colR, lede.r);

    // 2. The tentacles: where each leaves the rim, and the lane it then follows.
    var O = [], je = doc.querySelector(".jelly"), jb = je && box(je), fadeIn = jb && jb.w ? .3 * jb.h : 0;
    if (jb && jb.w) for (var i = 0; i < RIM.length; i += 2) O.push({ x: jb.l + RIM[i] * jb.w, y: jb.t + RIM[i + 1] * jb.h });
    if (!O.length) { svg.innerHTML = ""; root.classList.remove("has-trails"); return; }
    root.classList.add("has-trails");
    var margin = W - colR, trunks = [], stubs;
    // Each tentacle eases from the rim into its lane over Lt px; it is in the lane before the
    // first line of the hero's text that reaches out under it.
    var lines = [], rg = doc.createRange();
    [].forEach.call(doc.querySelectorAll(".title, .lede-col"), function (el) {
      var tw = doc.createTreeWalker(el, 4);
      while (tw.nextNode()) if (tw.currentNode.textContent.trim()) {
        rg.selectNodeContents(tw.currentNode);
        [].forEach.call(rg.getClientRects(), function (q) { if (q.width) lines.push({ t: q.top - P.top, r: q.right - P.left }); });
      }
    });
    function span(o, d) {
      var lim = lines.reduce(function (m, q) { return q.t > o.y && q.r > o.x - 14 ? Math.min(m, q.t) : m; }, 1e9);
      return lim < 1e9 ? Math.max(16, Math.min(d, lim - 10 - o.y)) : d;
    }
    // The tentacles nearest the margin carry on as a loose bunch: three, two, or on a phone one,
    // down the right edge. The next one in carries on too, as a strand of its own: its lane is G
    // lane-widths inward of the bunch, used only where both it and the bunch still clear the text
    // (xtra below: from a margin of about 47px, so not on a phone). It goes last in the list, so
    // the rules' rotation below reaches it (on a wide screen it curls into the last rule).
    var nB = Math.min(O.length, margin >= 150 ? 3 : margin >= 64 ? 2 : 1), G = 2.5,
        inL = small ? 15 : 22, outR = small ? 11 : 14;      // clearance from the text, and from the edge
    function laneW(g) { return Math.max(1, Math.min(16, (margin - 2 * (small ? 6 : 16)) / (1 + 1.5 * (nB - 1) + g))); }
    var A = laneW(G), xtra = nB < O.length && colR + inL + (1.5 * (nB - 1) + G) * A <= W - outR;
    if (!xtra) A = laneW(0);
    var use = O.slice(O.length - nB),
        mean = use.reduce(function (s, o) { return s + o.x; }, 0) / nB, half = (nB - 1) / 2 * A * 1.5,
        c0 = Math.min(Math.max(mean, colR + inL + half + (xtra ? G * A : 0)), W - outR - half),
        lanes = use.map(function (o, i) { return c0 + (i - (nB - 1) / 2) * A * 1.5; });
    if (xtra) { use.push(O[O.length - nB - 1]); lanes.push(c0 - half - G * A); }
    stubs = O.slice(0, O.length - use.length);
    use.forEach(function (o, i) {
      var r = rnd(31 + i), Lt = span(o, 220), own = i == nB;    // own: the strand inward of the bunch
      trunks.push({
        S: [o.x, o.y], Lt: Lt,
        lane: (function (x, a, l1, l2, ph) {   // a slowly varying sine: loosely intertwining
          return function (y) {
            var t = Math.min(Math.max((y - o.y) / Lt, 0), 1), s = t * t * (3 - 2 * t);
            return o.x * (1 - s) + s * (x + a * s * Math.sin(y / l1 + ph + 1.3 * Math.sin(y / l2 + ph)));
          };
        })(lanes[i], small ? 1 : A * (own ? .3 + .2 * r() : .5 + .4 * r()), 70 + 90 * r(), 260 + 260 * r(), i * 2.1 + r()),
        w0: small ? .85 : .95, w1: .5, e: r()
      });
    });
    // More tentacles hang from the left half of the rim, each in a lane of its own in the margin
    // between the text column and the strands above: lanes 2 lane-widths apart and G lane-widths
    // clear of those strands (28px at least), as many as fit, the ones nearest the margin first.
    // Where two or more fit, the outermost stops partway down, fading out, so it reads as a
    // shorter tentacle. Those that find no lane hang from the rim and fade out above the first
    // text or rule below them (on a phone, above the name).
    var nR = trunks.length, shorts = [], txt = [];
    [].forEach.call(doc.querySelectorAll("main"), function (el) {
      var tw = doc.createTreeWalker(el, 4);
      while (tw.nextNode()) if (tw.currentNode.textContent.trim() && !tw.currentNode.parentNode.closest("svg")) {
        rg.selectNodeContents(tw.currentNode);
        [].forEach.call(rg.getClientRects(), function (q) { if (q.width) txt.push({ t: q.top - P.top, l: q.left - P.left, r: q.right - P.left }); });
      }
    });
    function room(x0, x1, y) {  // how far a strand between x0 and x1 can hang below y
      var lim = H;
      txt.forEach(function (q) { if (q.t > y && q.r > x0 - 14 && q.l < x1 + 14) lim = Math.min(lim, q.t); });
      rules.forEach(function (R) { if (R.y > y && R.l < x1 + 14) lim = Math.min(lim, R.y); });
      return lim - y;
    }
    var OL = [], sp = Math.max(2 * A, 28), lo = colR + inL + A / 2,
        hi = Math.min.apply(null, lanes) - Math.max(G * A, 28), kL, prev = -1e9;
    for (i = 0; i < RIML.length; i += 2) OL.push({ x: jb.l + RIML[i] * jb.w, y: jb.t + RIML[i + 1] * jb.h });
    kL = hi >= lo ? Math.min(OL.length, Math.floor((hi - lo) / sp) + 1) : 0;
    OL.forEach(function (o, j) {
      var r = rnd(71 + j), k = j - (OL.length - kL), x = o.x;   // k >= 0: this one has a lane
      if (k >= 0) x = prev = Math.min(Math.max(o.x, lo + k * sp, prev + sp), hi - (kL - 1 - k) * sp);
      var a = k >= 0 ? A * (.35 + .2 * r()) : small ? 1.2 : 2 + 1.5 * r(), Lt = k >= 0 ? span(o, 220) : 60,
          l1 = 70 + 90 * r(), l2 = 260 + 260 * r(), ph = j * 2.3 + r();
      var T = {
        S: [o.x, o.y], Lt: Lt,
        lane: function (y) {   // as above; without a lane, it sways about the point it hangs from
          var t = Math.min(Math.max((y - o.y) / Lt, 0), 1), s = t * t * (3 - 2 * t);
          return o.x * (1 - s) + s * (x + a * s * Math.sin(y / l1 + ph + 1.3 * Math.sin(y / l2 + ph)));
        },
        w0: small ? .85 : .95, w1: .5
      };
      if (k < 0) {             // no lane: a short tentacle, above whatever is below it
        var d = Math.min(room(o.x - a, o.x + a, o.y) - (small ? 14 : 18), 1.4 * jb.h);
        T.stop = o.y + d * (.72 + .28 * r()); T.fi = .2 * (T.stop - o.y); T.fo = small ? .4 : .35;
        if (T.stop - o.y >= 24) shorts.push(T);
        return;
      }
      if (k == 0 && kL > 1) {   // partway down, ending at least 48px above or below a rule
        var e = o.y + (H - o.y) * (.5 + .12 * r());
        rules.forEach(function (R) { if (Math.abs(R.y - e) < 48) e = R.y - 48; });
        T.stop = e; T.fi = fadeIn; T.fo = .45;
      }
      T.e = r();
      trunks.push(T);
    });
    var y0w = Math.min.apply(null, trunks.map(function (T) { return T.S[1]; }));
    trunks.forEach(function (T) {
      // the tentacle down to the foot of the page (cut to length later), with arc lengths so
      // the draw-in can time each curl to the moment the tentacle reaches it
      var S = T.S, Q = [], cum = [0], j;
      T.yM = S[1];
      for (var y = S[1]; y < H; y += y < S[1] + T.Lt ? 1.5 : 5) Q.push(T.lane(y), y);
      for (j = 2; j < Q.length; j += 2) cum.push(cum[j / 2 - 1] + Math.hypot(Q[j] - Q[j - 2], Q[j + 1] - Q[j - 1]));
      T.Q = Q;
      T.ms = function (y) { for (var j = 0; j < cum.length - 1 && Q[2 * j + 1] < y; j++); return Math.round(cum[j] / SPEED); };
    });

    // 3. Each rule: a tentacle peeling off in a curl, or a plain hairline when none can reach it.
    var defs = [], br = [], tks = [];
    function clear(Q, R) {      // a path stays off the text above rule R
      for (var j = 0; j < Q.length; j += 2) if (Q[j] < R.r + 6 && Q[j + 1] < R.above + 10) return false;
      return true;
    }

    rules.forEach(function (R, k2) {
      var id = "tr" + k2, nT = trunks.length, done = false;
      for (var t = 0; t < nT && !done; t++) {
        // the strands on the right take the rules in turn; one from the left only if none can
        var T = trunks[t < nR ? (k2 + 1 + t) % nR : t];
        if (T.stop) continue;
        // A tentacle leaves along the trunk, curls 1.25 turns and runs flat to the column's
        // left edge, thinning out and fading to nothing over its last 2rem. The thinning is
        // carried by opacity: a filled ribbon narrower than a device pixel is rasterised with
        // a visible brightness step where it crosses that width.
        for (var sc = 1; sc > .4 && !done; sc -= .3) {
          var rf = tear(16 * sc, 7 * sc, 22 * sc, .55), cl = coil(PI / 2, 1.25, rf, 1, true), y1 = R.y - cl.end[1], x1 = T.lane(y1);
          if (y1 < T.yM + fadeIn * .8) break;
          var dx = T.lane(y1 + 2) - T.lane(y1 - 2), th = Math.atan2(4, dx);
          cl = coil(th, 1.25 + (PI / 2 - th) / (2 * PI), rf, 1, true);
          y1 = R.y - cl.end[1]; x1 = T.lane(y1);
          var Q2 = shift(cl.P, x1, y1);
          Q2[Q2.length - 1] = R.y;
          if (Q2[Q2.length - 2] < R.l + 3 * rem || !clear(Q2, R)) continue;
          var xc = Q2[Q2.length - 2], xr = Math.max.apply(null, Q2.filter(function (v, k) { return !(k % 2); })), span = xr - R.l;
          for (var xx = xc - 8; xx > R.l; xx -= 8) Q2.push(xx, R.y);
          Q2.push(R.l, R.y);
          defs.push('<linearGradient id="' + id + '" gradientUnits="userSpaceOnUse" x1="' + n(R.l) + '" y1="0" x2="' + n(xr) +
                    '" y2="0"><stop class="z"/><stop offset="' + n(2 * rem / span) + '" class="h"/><stop offset="' + n(Math.max(2 * rem, xc - R.l) / span) +
                    '" class="a"/><stop offset="1" class="a"/></linearGradient>');
          br.push('<path class="cu' + (anim ? ' fade" style="--dl:' + T.ms(y1) + 'ms' : "") + '" data-rule="' + R.id + '" fill="url(#' + id + ')" d="' +
                  ribbon(Q2, function (u) { return 1.25 - .25 * Math.min(1, u * 1.15); }) + '"/>');
          T.last = y1;
          done = true;
        }
      }
      if (!done) br.push('<path class="rl' + (anim ? ' grow" pathLength="1" style="--dl:' + Math.round(Math.max(0, R.y - y0w) / SPEED) + 'ms' : "") +
                         '" data-rule="' + R.id + '" d="M' + n(R.r) + " " + R.y + "H" + n(R.l) + '"/>');
    });

    // 4. The tentacles themselves, as tapering ribbons that thin out and fade to nothing: a long
    //    one over its last FADE rem, below the last rule it curls into and a little above the foot
    //    of the page; one that stops short (T.stop) over its last part (T.fo).
    function drawIn(g, Q, tot, id) {   // one-time draw-in: a mask stroke grows along the tentacle
      if (!anim) return g;
      defs.push('<mask id="' + id + '" maskUnits="userSpaceOnUse" x="0" y="0" width="' + n(W) + '" height="' + n(H) +
                '"><path class="grow lin" pathLength="1" style="--du:' + Math.round(tot / SPEED) + 'ms" fill="none" stroke="#fff" stroke-width="40" d="' +
                poly(Q) + '"/></mask>');
      return '<g mask="url(#' + id + ')">' + g + "</g>";
    }
    function fading(T, id) {
      var S = T.S, Q = [], len = T.stop - S[1];
      for (var y = S[1]; y < T.stop; y += 1.5) Q.push(T.lane(y), y);
      Q.push(T.lane(T.stop), T.stop);
      var f1 = Math.min(T.fi / len, 1 - T.fo);
      defs.push('<linearGradient id="' + id + '" gradientUnits="userSpaceOnUse" x1="0" y1="' + n(S[1]) + '" x2="0" y2="' + n(T.stop) +
                '"><stop class="z"/><stop offset="' + n(f1) + '" class="a"/><stop offset="' + n(1 - T.fo) + '" class="a"/><stop offset="1" class="z"/></linearGradient>');
      tks.push(drawIn('<path fill="url(#' + id + ')" d="' + ribbon(Q, function (u) { return T.w0 + (.35 - T.w0) * u; }) + '"/>',
                      Q, cumul(Q).pop(), "m" + id));
    }
    trunks.forEach(function (T, i) {
      if (T.stop) return fading(T, "tk" + i);
      // it ends 1.5-3.5rem above the foot of the page (each strand its own), and starts to fade
      // FADE rem before that, but never above its last curl, so each curl leaves it at full strength
      var S = T.S, end = H - (1.5 + 2 * T.e) * rem, len = end - S[1], Q = [],
          fs = Math.min(Math.max(end - FADE * rem, T.last || 0, S[1] + fadeIn), end - 2 * rem);
      for (var j = 0; j < T.Q.length && T.Q[j + 1] < end; j += 2) Q.push(T.Q[j], T.Q[j + 1]);
      Q.push(T.lane(end), end);
      var c = cumul(Q), tot = c[c.length - 1], sF = tot;   // sF: arc length where the fade begins
      for (j = 0; j < c.length; j++) if (Q[2 * j + 1] >= fs) { sF = c[j]; break; }
      defs.push('<linearGradient id="tk' + i + '" gradientUnits="userSpaceOnUse" x1="0" y1="' + n(S[1]) + '" x2="0" y2="' + n(end) +
                '"><stop class="z"/><stop offset="' + n(fadeIn / len) + '" class="a"/><stop offset="' + n((fs - S[1]) / len) +
                '" class="a"/><stop offset="1" class="z"/></linearGradient>');
      tks.push(drawIn('<path fill="url(#tk' + i + ')" d="' + ribbon(Q, function (u, s) {
        if (s > sF) return T.w1 + (.3 - T.w1) * (s - sF) / (tot - sF);   // the fade thins out too
        return T.w0 + (T.w1 - T.w0) * s / (sF || 1);
      }) + '"/>', Q, tot, "tm" + i));
    });
    shorts.forEach(function (T, i) { fading(T, "sh" + i); });
    // tentacles that do not carry on (narrow screens) fade out just below the rim
    stubs.forEach(function (o, i) {
      var Q = [], len = small ? 34 : 56, id = "st" + i;
      for (var y = 0; y <= len; y += 3) Q.push(o.x + 1.5 * Math.sin(y / 14 + i), o.y + y);
      defs.push('<linearGradient id="' + id + '" gradientUnits="userSpaceOnUse" x1="0" y1="' + n(o.y) + '" x2="0" y2="' + n(o.y + len) +
                '"><stop class="z"/><stop offset=".4" class="h"/><stop offset="1" class="z"/></linearGradient>');
      tks.push('<path fill="url(#' + id + ')" d="' + ribbon(Q, function (u) { return .95 - .6 * u; }) + '"/>');
    });

    svg.setAttribute("width", W); svg.setAttribute("height", H);
    svg.setAttribute("viewBox", "0 0 " + n(W) + " " + n(H));
    svg.innerHTML = "<defs>" + defs.join("") + '</defs><g class="glow">' + br.join("") + '<g class="tk">' + tks.join("") + "</g></g>";
  }

  function schedule() {         // next frame, or soon anyway (frames may not come in a hidden tab)
    if (!queued) { queued = true; requestAnimationFrame(draw); setTimeout(draw, 150); }
  }
  function start() { if (!ready) { ready = true; schedule(); } }
  function resized() {
    var r = page.getBoundingClientRect();
    if (r.width + "x" + r.height != drawn) schedule();
  }
  new ResizeObserver(resized).observe(page);
  addEventListener("resize", resized);    // in case resize observations wait for a frame that never comes
  // Draw once the fonts are in, or after 3s without them; if they come in later than that, the text
  // has moved under the tentacles, so draw again.
  (doc.fonts && doc.fonts.ready ? doc.fonts.ready : Promise.resolve()).then(function () { if (ready) schedule(); else start(); }, start);
  setTimeout(start, 3000);
})();
