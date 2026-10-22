#!/usr/bin/env python3
"""
scripts/medusa.py: jellyfish generator for hannapalya.com, used by scripts/build_illustrations.py.

Draws a moon jellyfish (Aurelia aurita) in fine hairlines as SVG:
  * a domed bell modelled in 3D and projected orthographically from above-front,
  * 16 radial canals: 8 unbranched, 8 that bifurcate *recursively* toward the rim
    (each canal splits into two narrower canals until it meets the ring canal),
  * four horseshoe gonads with folded inner tissue,
  * a scalloped margin with eight notches and rhopalia,
  * a fringe of tapered tentacles (taper = stacked stroke widths): ~96 long ones in loose
    drifts over a dense brush of 150 short marginal ones, so the rim doesn't read as a comb,
  * four frilled oral arms: twisting curtains whose margins are gathered twice (broad
    folds carrying small lace scallops), with pleats and blunt, rounded tips.

Outputs (into OUT_DIR):
  layer-back.svg, layer-bell.svg, layer-arms.svg, layer-front.svg  -- the four stacked layers
  layers.css   -- stroke widths / opacities per class (kept in assets/css/site.css)

Colours are never baked into the layers: paths carry classes (j-*) and assets/css/site.css
sets stroke/fill from its custom properties (--jelly, --jelly-gonad, ...).

Usage: python3 medusa.py [--seed N]
"""
import math, os, random, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = HERE

SEED = 5
if '--seed' in sys.argv:
    SEED = int(sys.argv[sys.argv.index('--seed') + 1])
rng = random.Random(SEED)

# ------------------------------------------------------------------ geometry ---
VW, VH = 600, 860           # viewBox
S = 236.0                   # pixels per bell radius
CX, CY = 312.0, 180.0       # screen position of the rim-plane centre
PHI = math.radians(33)      # camera elevation (looking down onto the bell)
HB = 0.50                   # dome height, in bell radii
ROT = math.radians(22)      # rotation of the body plan about the bell axis
SPH, CPH = math.sin(PHI), math.cos(PHI)


def dome_z(r):
    r = np.clip(np.asarray(r, dtype=float), 0.0, 1.0)
    return HB * (1.0 - r ** 2) ** 0.85


def dome_dz(r, h=1e-4):
    r = np.asarray(r, float)
    return (dome_z(np.minimum(r + h, 1.0)) - dome_z(np.maximum(r - h, 0.0))) / (2 * h)


def proj(x, y, z):
    """3D -> screen (y down). The viewer sits at -y, above the bell."""
    return CX + S * np.asarray(x), CY - S * (np.asarray(y) * SPH + np.asarray(z) * CPH)


def facing(r, th):
    """> 0 where the dome surface faces the viewer."""
    return dome_dz(r) * np.sin(th) * CPH + SPH


def on_dome(r, th, lift=0.0):
    r = np.asarray(r, float); th = np.asarray(th, float)
    return proj(r * np.cos(th), r * np.sin(th), dome_z(r) + lift)


# ------------------------------------------------------------- path output ---
def rdp(pts, eps):
    """Ramer-Douglas-Peucker polyline simplification (iterative)."""
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return pts.tolist()
    keep = np.zeros(len(pts), bool); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 - i0 < 2:
            continue
        a, b = pts[i0], pts[i1]
        ab = b - a; n = math.hypot(*ab)
        P = pts[i0 + 1:i1]
        d = np.hypot(*(P - a).T) if n == 0 else np.abs(ab[0] * (P[:, 1] - a[1]) - ab[1] * (P[:, 0] - a[0])) / n
        j = int(np.argmax(d))
        if d[j] > eps:
            k = i0 + 1 + j; keep[k] = True
            stack += [(i0, k), (k, i1)]
    return pts[keep].tolist()


def num(v):
    s = f'{v:.1f}'
    if s.endswith('.0'):
        s = s[:-2]
    if s == '-0':
        s = '0'
    s = s.replace('-0.', '-.')
    if s.startswith('0.'):
        s = s[1:]
    return s


def join_nums(vals):
    """Concatenate path numbers with the minimum separators SVG allows."""
    out, prev = '', None
    for v in vals:
        if prev is not None and not (v.startswith('-') or (v.startswith('.') and '.' in prev)):
            out += ' '
        out += v
        prev = v
    return out


def poly_d(pts, eps=0.15, closed=False):
    """Polyline -> compact path data: absolute M, then relative l, on a 0.1px grid."""
    if len(pts) < 2:
        return ''
    pts = rdp(pts, eps)
    q = [(round(x * 10), round(y * 10)) for x, y in pts]
    dq = [q[0]]
    for p in q[1:]:
        if p != dq[-1]:
            dq.append(p)
    if len(dq) < 2:
        return ''
    d = 'M' + join_nums([num(dq[0][0] / 10), num(dq[0][1] / 10)])
    rel = []
    for (x0, y0), (x1, y1) in zip(dq, dq[1:]):
        rel += [num((x1 - x0) / 10), num((y1 - y0) / 10)]
    d += 'l' + join_nums(rel) + ('z' if closed else '')
    return d


class Bucket:
    """Collects polylines per CSS class; each class becomes one <path>."""
    def __init__(self):
        self.d = {}

    bounds = [1e9, 1e9, -1e9, -1e9]

    def add(self, cls, pts, eps=0.15, closed=False):
        if len(pts) >= 2:
            a = np.asarray(pts, float); B = Bucket.bounds
            B[:] = [min(B[0], a[:, 0].min()), min(B[1], a[:, 1].min()), max(B[2], a[:, 0].max()), max(B[3], a[:, 1].max())]
            self.d.setdefault(cls, []).append(poly_d(pts, eps, closed))

    def svg_paths(self, order):
        return ''.join(f'<path class="{k}" d="{"".join(self.d[k])}"/>' for k in order if k in self.d)


def split_by(pts, flags):
    """Split a polyline into runs of equal flag value (runs share their boundary point)."""
    runs, cur, cf = [], [pts[0]], flags[0]
    for p, f in zip(pts[1:], flags[1:]):
        cur.append(p)
        if f != cf:
            runs.append((cf, cur))
            cur, cf = [p], f
    runs.append((cf, cur))
    return runs


def surf_line(bucket, r, th, cls_front, cls_back, lift=0.0, eps=0.15):
    """A line lying on the dome: front-facing and back-facing parts get different classes."""
    X, Y = on_dome(r, th, lift)
    f = facing(np.asarray(r), np.asarray(th)) > 0
    for ff, run in split_by(list(zip(X, Y)), list(f)):
        bucket.add(cls_front if ff else cls_back, run, eps)


# ---------------------------------------------------------------- the bell ---
bell = Bucket()
NOTCH = [ROT + math.radians(22.5 + 45 * k) for k in range(8)]   # rhopalia between lobes
N_SCALLOP = 56


def rim_r(th):
    th = np.asarray(th, float)
    r = np.ones_like(th)
    for a in NOTCH:
        dd = np.angle(np.exp(1j * (th - a)))
        # a notch that sits on the left/right limb is seen edge-on, so it barely dents the outline
        r = r - 0.03 * (0.2 + 0.8 * min(1.0, 4 * abs(math.sin(a)))) * np.exp(-(dd / 0.05) ** 2)
    return r


def rim_z(th):
    """Each scallop of the margin hangs as a small arc between cusps."""
    u = (np.asarray(th, float) * N_SCALLOP / (2 * math.pi)) % 1.0
    return -0.024 * np.sin(math.pi * u) ** 0.7


# silhouette: upper envelope of the projected dome; lower edge is the front margin
SIL_X = np.linspace(-1, 1, 401)
_ys = np.linspace(-1, 1, 1601)
SIL_TOP = np.array([CY - S * (_ys[np.hypot(x, _ys) <= 1] * SPH +
                              dome_z(np.hypot(x, _ys[np.hypot(x, _ys) <= 1])) * CPH).max() for x in SIL_X])
SIL_BOT = CY + S * np.sqrt(np.clip(1 - SIL_X ** 2, 0, 1)) * SPH + S * 0.02


def inside_bell(x, y, pad=0.0):
    u = (np.asarray(x) - CX) / S
    ok = np.abs(u) < 1
    top = np.interp(u, SIL_X, SIL_TOP); bot = np.interp(u, SIL_X, SIL_BOT)
    return ok & (np.asarray(y) > top - pad) & (np.asarray(y) < bot + pad)


bell.add('j-edge', list(zip(CX + S * SIL_X, SIL_TOP)), eps=0.08)

# margin: front half strong, back half seen through the bell
th = np.linspace(-math.pi, math.pi, 2001)
rr = rim_r(th)
X, Y = proj(rr * np.cos(th), rr * np.sin(th), rim_z(th))
for ff, run in split_by(list(zip(X, Y)), list(np.sin(th) < 0)):
    bell.add('j-edge' if ff else 'j-back', run, eps=0.06)

# ring canal (just inside the margin)
R_RING = 0.955
th = np.linspace(-math.pi, math.pi, 900)
surf_line(bell, R_RING * rim_r(th), th, 'j-canal2', 'j-back', eps=0.1)

# rhopalia: tiny knobs in the notches
rho = []
for a in NOTCH:
    r0 = rim_r(a) + 0.004
    x, y = proj(r0 * math.cos(a), r0 * math.sin(a), -0.012)
    rho.append((float(x), float(y), math.sin(a) < 0))

# radial canals -----------------------------------------------------------------
SPLITS = [0.53, 0.68, 0.80, 0.885]      # radii at which branched canals bifurcate
CANAL_CLS = ['j-canal0', 'j-canal1', 'j-canal2', 'j-canal3', 'j-canal4']


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def canal(r0, th0, th1, level, hw, max_level):
    """Recursive canal: run outward from (r0, th0) while easing toward angle th1,
    then split into two children, each fanning over half of the remaining sector.
    Split radii, spreads and a faint meander are jittered so the lattice looks grown."""
    r1 = R_RING if level >= max_level else SPLITS[level] + rng.uniform(-0.025, 0.025)
    n = max(12, int((r1 - r0) * 120))
    t = np.linspace(0, 1, n)
    r = r0 + (r1 - r0) * t
    wob = 0.004 * math.sin(rng.uniform(0, 6)) * np.sin(math.pi * t * rng.uniform(1, 2.5))
    ang = th0 + (th1 - th0) * np.sin(0.5 * math.pi * np.clip(t / rng.uniform(0.55, 0.75), 0, 1)) + wob
    if level >= max_level:
        r = r * np.interp(t, [0, 0.6, 1], [1, 1, 0]) + R_RING * rim_r(ang) * np.interp(t, [0, 0.6, 1], [0, 0, 1])
    surf_line(bell, r, ang, CANAL_CLS[level], 'j-back')
    if level < max_level:
        for sgn in (-1, 1):
            spread = hw / 2 * rng.uniform(0.75, 1.15)
            canal(r1, th1, th1 + sgn * spread, level + 1, hw / 2, max_level)


RG, RHO, DEL = 0.255, 0.10, 0.026      # gonad centre radius, horseshoe radius, half-thickness
HW = math.radians(18)
for k in range(4):
    per = ROT + math.radians(90 * k)           # perradial canals start between gonads
    inter = ROT + math.radians(45 + 90 * k)    # interradial ones at the gonad's outer edge
    canal(0.09, per, per, 0, HW, 4)
    canal(RG + RHO + DEL, inter, inter, 0, HW, 4)
for k in range(8):                              # adradial canals: unbranched
    a = ROT + math.radians(22.5 + 45 * k)
    r = np.linspace(0.30, R_RING, 70)
    surf_line(bell, r * np.interp(r, [0.3, 0.9, R_RING], [1, 1, rim_r(a)]), np.full_like(r, a), 'j-canal1', 'j-back')

# gonads: four horseshoes, open toward the centre -------------------------------
for k in range(4):
    g = ROT + math.radians(45 + 90 * k)
    u = np.array([math.cos(g), math.sin(g)]); v = np.array([-math.sin(g), math.cos(g)])
    c = RG * u
    A0 = math.radians(142)

    def P(rad, al):
        return c[:, None] + rad * (np.cos(al)[None, :] * u[:, None] + np.sin(al)[None, :] * v[:, None])
    al = np.linspace(-A0, A0, 200)
    tp = np.sqrt(np.clip(1 - (al / A0) ** 8, 0, 1))
    ring = np.concatenate([P(RHO + DEL * tp, al), P(RHO - DEL * tp, al)[:, ::-1]], axis=1)
    X, Y = on_dome(np.hypot(*ring), np.arctan2(ring[1], ring[0]), 0.004)
    bell.add('j-gonad', list(zip(X, Y)), eps=0.08, closed=True)
    # gonad tissue: a string of fine dots along the band's centre line
    al2 = np.linspace(-A0 * 0.9, A0 * 0.9, 25)
    mid = P(np.full_like(al2, RHO), al2)
    X, Y = on_dome(np.hypot(*mid), np.arctan2(mid[1], mid[0]), 0.004)
    for x_, y_ in zip(X, Y):
        bell.d.setdefault('j-dots', []).append(f'M{num(x_)} {num(y_)}h0')

# central stomach (four-lobed cross)
a = np.linspace(0, 2 * math.pi, 240)
rs = 0.075 * (1 + 0.22 * np.cos(4 * (a - ROT)))
X, Y = on_dome(rs, a, 0.002)
bell.add('j-canal1', list(zip(X, Y)), eps=0.08, closed=True)


# --------------------------------------------------------------- tentacles ---
back = Bucket(); fronttent = Bucket()
TAPER = [(0.00, 0.2), (0.2, 0.45), (0.45, 0.72), (0.72, 1.0)]


def tentacle(bucket, prefix, x0, y0, out, L, phase, amp, freq, drift, lean0=0.0, clip_bell=False,
             n=64, taper=None):
    taper = taper or list(enumerate(TAPER))
    t = np.linspace(0, 1, n)
    flare = out * S * 0.07 * (1 - (1 - np.minimum(t * 3.0, 1)) ** 2)   # leave the rim outward
    wave = amp * S * t ** 1.15 * np.sin(2 * math.pi * freq * t + phase)
    wave2 = 0.28 * amp * S * t ** 1.6 * np.sin(2 * math.pi * 2.3 * freq * t + 1.9 * phase)
    x = x0 + flare + wave + wave2 + drift * S * t ** 1.8 + lean0 * S * t
    y = y0 + L * S * t
    pts = np.stack([x, y], 1)
    vis = ~inside_bell(x, y, pad=-1.5) if clip_bell else np.ones(n, bool)
    for i, (a_, b_) in taper:
        i0, i1 = int(round(a_ * (n - 1))), int(round(b_ * (n - 1)))
        seg, sv = pts[i0:i1 + 1], vis[i0:i1 + 1]
        for f, run in split_by([tuple(p) for p in seg], list(sv)):
            if f:
                bucket.add(f'{prefix}{i}', run, eps=0.14)


def hem(a):
    """Smooth 'noise' around the margin so long and short tentacles come in drifts."""
    return 0.5 + 0.5 * (0.6 * math.sin(3 * a + 1.3) + 0.4 * math.sin(7 * a + 4.1))


NT = 96
for i in range(NT):
    a = -math.pi + 2 * math.pi * (i + 0.9 * rng.random()) / NT
    a += 0.03 * math.sin(6 * a + 0.7)                   # bunch the long ones into loose drifts
    r0 = rim_r(a) * 0.99
    x0, y0 = proj(r0 * math.cos(a), r0 * math.sin(a), rim_z(a) - 0.006)
    fr = math.sin(a) < -0.05
    L = 0.28 + 0.55 * hem(a) * rng.uniform(0.45, 1.0) + (rng.uniform(0.3, 0.6) if rng.random() < 0.14 else 0)
    L *= 1.0 + 0.15 * max(0, -math.sin(a))            # front ones read a little longer
    phase = 1.1 * a + rng.uniform(-1.2, 1.2)            # neighbours sway roughly together
    amp = rng.uniform(0.02, 0.075)
    freq = rng.uniform(0.7, 1.3)
    drift = -0.13 + rng.uniform(-0.07, 0.07) + 0.04 * math.cos(a)
    lean0 = rng.uniform(-0.13, 0.07)
    if fr and rng.random() < 0.6:
        tentacle(fronttent, 'j-tf', float(x0), float(y0), math.cos(a), L, phase, amp, freq, drift, lean0)
    elif fr:   # a fainter, 'deeper' share of the front fringe breaks up the comb
        tentacle(back, 'j-tb', float(x0), float(y0), math.cos(a), L, phase, amp, freq, drift, lean0)
    else:
        tentacle(back, 'j-tb', float(x0), float(y0), math.cos(a), L * 0.9, phase, amp, freq, drift, lean0, clip_bell=True)

# the dense marginal fringe: many short, fine tentacles (the real animal has hundreds)
rng_f = random.Random(SEED + 101)
NS = 150
SHORT_TAPER = [(2, (0.0, 0.45)), (3, (0.45, 1.0))]
for i in range(NS):
    a = -math.pi + 2 * math.pi * (i + rng_f.random()) / NS
    r0 = rim_r(a) * 0.99
    x0, y0 = proj(r0 * math.cos(a), r0 * math.sin(a), rim_z(a) - 0.006)
    fr = math.sin(a) < -0.05
    L = rng_f.uniform(0.05, 0.16) * (0.8 + 0.5 * hem(a + 1.0))
    args = (float(x0), float(y0), 0.6 * math.cos(a), L, rng_f.uniform(0, 6), rng_f.uniform(0.01, 0.03),
            rng_f.uniform(0.6, 1.0), -0.06 + rng_f.uniform(-0.05, 0.05), rng_f.uniform(-0.08, 0.06))
    if fr and rng_f.random() < 0.7:
        tentacle(fronttent, 'j-tf', *args, n=16, taper=SHORT_TAPER)
    else:
        tentacle(back, 'j-tb', *args, clip_bell=not fr, n=16, taper=SHORT_TAPER)


# --------------------------------------------------------------- oral arms ---
arms = Bucket()


def oral_arm(xb, yb, length, lean, bend, phase, width, seed):
    """A frilled oral arm: a slender curtain that hangs from the mouth and twists.
    Each margin is gathered twice over -- broad folds (the curtain swinging in and out)
    carrying a chain of small lace scallops -- with a second, fainter scalloped line just
    inside it (the far layer of the frill), pleats running in from the broad folds, and
    a blunt, rounded tip rather than a leaf-like point."""
    r_ = random.Random(seed)
    n = 1400
    t = np.linspace(0, 1, n)
    sx = xb + S * (lean * t ** 1.5 + bend * np.sin(math.pi * 1.25 * t + phase) * t ** 0.8)
    sy = yb + S * length * t
    dx, dy = np.gradient(sx), np.gradient(sy)
    nn = np.hypot(dx, dy); tx, ty = dx / nn, dy / nn
    nx, ny = -ty, tx
    twist = np.cos(math.pi * (1.35 * t + 0.12 * phase))
    rise = np.sin(0.5 * math.pi * np.clip(t / 0.1, 0, 1)) ** 0.6
    tip = np.sqrt(np.clip(1 - (np.clip(t - 0.86, 0, None) / 0.14) ** 2, 0, 1))
    w = S * width * (0.8 + 0.2 * np.sin(math.pi * t)) * (1 - 0.3 * t) * rise * tip
    arclen = np.concatenate([[0], np.cumsum(np.hypot(np.diff(sx), np.diff(sy)))])
    inside = inside_bell(sx, sy, pad=-2)
    out = ~inside

    def put(cls, xs_, ys_, eps):
        for f, run in split_by(list(zip(xs_, ys_)), list(inside)):
            arms.add(cls + ('-in' if f else ''), run, eps)

    W0 = w * (0.5 + 0.5 * np.abs(twist))                  # narrower where the arm twists
    for side in (-1, 1):
        c1, c2, c3 = r_.uniform(0, 6), r_.uniform(0, 6), r_.uniform(0, 6)
        # broad folds of the curtain (wavelength ~30px, different on each side)
        big = np.sin(2 * math.pi * np.cumsum(np.gradient(arclen) / (27 + 8 * np.sin(arclen / 50 + c3))) + c3)
        W = W0 * (1 + 0.16 * big * out)
        # small lace scallops riding on the folds
        freq = (1 / 8.0) * (1 + 0.25 * np.sin(arclen / 31 + c1))
        psi = math.pi * np.cumsum(freq * np.gradient(arclen)) + c2
        amp = (0.15 * w + 1.3) * (0.7 + 0.3 * big) * out * np.clip(w / 3, 0, 1)
        lace = amp * np.abs(np.sin(psi)) ** 0.75
        off = side * (W + lace)
        put('j-frill', sx + nx * off, sy + ny * off, 0.07)
        lace2 = 0.65 * amp * np.abs(np.sin(psi + math.pi / 2)) ** 0.75
        off2 = side * (W - 1.5 - 0.22 * w + lace2)
        m2 = out & (t < 0.86) & (W > 4)
        for f, run in split_by(list(zip(sx + nx * off2, sy + ny * off2)), list(m2)):
            if f and len(run) > 6:
                arms.add('j-frill2', run, 0.08)
        # pleats: from the crest of each broad fold a crease runs in and down
        for i in np.nonzero((big[1:-1] > big[:-2]) & (big[1:-1] >= big[2:]))[0] + 1:
            if inside[i] or not (0.06 < t[i] < 0.84) or W0[i] < 5:
                continue
            u = np.linspace(0, 1, 9)
            k = r_.uniform(0.45, 0.8)
            dn = side * (W[i] - 1.0) * (1 - k * u)
            dt = (6 + 0.5 * w[i]) * u * r_.uniform(0.8, 1.3)
            arms.add('j-drape', list(zip(sx[i] + nx[i] * dn + tx[i] * dt, sy[i] + ny[i] * dn + ty[i] * dt)), 0.05)


mx, my = proj(0, 0, 0.05)
mx, my = float(mx), float(my)
ARMS = [  # x-offset, length, lean, bend, phase, width
    (-0.09, 1.00, -0.22, 0.09, 0.4, 0.075),
    (-0.03, 1.30, -0.12, 0.11, 2.1, 0.085),
    (0.035, 1.18, -0.05, 0.10, 4.0, 0.080),
    (0.10, 0.94, 0.02, 0.08, 5.4, 0.070),
]
for i, (off, L, lean, bend, ph, wd) in enumerate(ARMS):
    oral_arm(mx + S * off, my, L, lean, bend, ph, wd, SEED * 10 + i)


# -------------------------------------------------------------- write SVGs ---
B_ = Bucket.bounds
VB = (math.floor(B_[0] - 18), math.floor(B_[1] - 18), math.ceil(B_[2] - B_[0] + 36), math.ceil(B_[3] - B_[1] + 36))
VBS = ' '.join(map(str, VB))


def svg_wrap(body, cls):
    return (f'<svg class="{cls}" viewBox="{VBS}" xmlns="http://www.w3.org/2000/svg" '
            f'aria-hidden="true" focusable="false">{body}</svg>')


rho_svg = ''.join(f'<circle class="{"j-rho" if f else "j-rhob"}" cx="{num(x)}" cy="{num(y)}" r="1.8"/>' for x, y, f in rho)
BELL_ORDER = ['j-back', 'j-canal4', 'j-canal3', 'j-canal2', 'j-canal1', 'j-canal0', 'j-dots', 'j-gonad', 'j-edge']
layers = {
    'back': back.svg_paths([f'j-tb{i}' for i in range(4)]),
    'bell': bell.svg_paths(BELL_ORDER) + rho_svg,
    'arms': arms.svg_paths(['j-frill-in', 'j-drape', 'j-frill2', 'j-frill']),
    'front': fronttent.svg_paths([f'j-tf{i}' for i in range(4)]),
}
total = 0
for k, body in layers.items():
    s = svg_wrap(body, f'jl jl-{k}')
    open(os.path.join(OUT_DIR, f'layer-{k}.svg'), 'w').write(s)
    total += len(s)
    print(f'layer-{k}.svg  {len(s)/1024:.1f} KB')
print(f'hero total {total/1024:.1f} KB; viewBox', VBS)


# ------------------------------------------------- per-class line styling ---
LAYER_CSS = """
.jl path{fill:none;stroke:var(--jelly);stroke-linecap:round;stroke-linejoin:round}
.jl-back path,.jl-front path{stroke-linecap:butt}
.jl .j-edge{stroke-width:calc(1.15px * var(--jk, 1) * var(--js, 1) * var(--jd, 1))}
.jl .j-back{stroke-width:calc(.6px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.3}
.jl .j-canal0{stroke-width:calc(1.05px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.92}
.jl .j-canal1{stroke-width:calc(.85px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.82}
.jl .j-canal2{stroke-width:calc(.68px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.75}
.jl .j-canal3{stroke-width:calc(.55px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.68}
.jl .j-canal4{stroke-width:calc(.45px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.6}
.jl .j-gonad{stroke:var(--jelly-gonad);stroke-width:calc(.95px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));fill:var(--jelly-gonad-fill)}
.jl .j-dots{stroke:var(--jelly-gonad);stroke-width:calc(1.9px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.9}
.jl .j-rho{fill:var(--jelly);stroke:none}
.jl .j-rhob{fill:var(--jelly);stroke:none;opacity:.35}
.jl .j-frill{stroke-width:calc(.75px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.9}
.jl .j-drape{stroke-width:calc(.5px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.5}
.jl .j-frill-in{stroke-width:calc(.5px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.2}
.jl .j-frill2{stroke-width:calc(.45px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.55}
.jl .j-tf0{stroke-width:calc(.85px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.78}
.jl .j-tf1{stroke-width:calc(.7px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.66}
.jl .j-tf2{stroke-width:calc(.56px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.55}
.jl .j-tf3{stroke-width:calc(.36px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.36}
.jl .j-tb0{stroke-width:calc(.8px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.55}
.jl .j-tb1{stroke-width:calc(.62px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.42}
.jl .j-tb2{stroke-width:calc(.46px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.3}
.jl .j-tb3{stroke-width:calc(.32px * var(--jk, 1) * var(--js, 1) * var(--jd, 1));opacity:.2}
""".strip()
open(os.path.join(OUT_DIR, 'layers.css'), 'w').write(LAYER_CSS)
