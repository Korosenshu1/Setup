#!/usr/bin/env python3
"""
fit_legge.py - Fit ai minimi quadrati di dati con una legge scritta dall'utente.

Dati in ingresso:
  - file di testo/CSV a colonne (separatori: spazi, tab, virgola, punto e virgola);
    le righe non numeriche (intestazioni, commenti #) vengono ignorate;
  - spettri MAESTRO .Spe (x = canale o energia se calibrato, y = conteggi,
    sigma = sqrt(conteggi)), con selezione dell'intervallo;
  - dati inseriti a mano nel terminale.

Legge: qualunque espressione in x, ad es.
    a*exp(-b*x) + c
    A*exp(-(x-mu)**2/(2*s**2)) + p0 + p1*x
    sqrt(a + b*x + c*x**2)
Sono disponibili exp, log, log10, sqrt, sin, cos, tan, pi, abs ecc.
I parametri sono riconosciuti automaticamente (tutti i simboli diversi da x).
Sono anche pronte alcune leggi con nome: digita "leggi" nel prompt.

Uso interattivo:        python fit_legge.py
Uso da riga di comando: python fit_legge.py dati.csv --x 0 --y 1 --sy 2 \
                            --legge "a + b*x + c*x**2" --p0 "a=0,b=1,c=0"
                        python fit_legge.py cesio137.Spe --range 340 440 \
                            --legge gauss_lin --p0 "A=1e4,mu=388,s=13"

Grandezze derivate: --derivate "area=A*s*sqrt(2*pi)+2*b*T; fwhm=2.3548*s"
calcola funzioni dei parametri con incertezza propagata dalla covarianza.

Uscite (cartella --outdir): grafico con residui (.png), report (.txt),
curva fittata e residui (.csv).
"""
import argparse
import os
import re
import sys

import numpy as np
import sympy as sp
from scipy import stats
from scipy.optimize import curve_fit

# --------------------------------------------------------------------------
# Leggi predefinite (utili in spettroscopia gamma)
# --------------------------------------------------------------------------
LEGGI = {
    "lineare":     ("a + b*x", "retta (es. calibrazione)"),
    "quadratica":  ("a + b*x + c*x**2", "parabola (calibrazione non lineare)"),
    "gauss":       ("A*exp(-(x-mu)**2/(2*s**2))", "gaussiana"),
    "gauss_lin":   ("A*exp(-(x-mu)**2/(2*s**2)) + p0 + p1*(x-mu)", "fotopicco su fondo lineare"),
    "gauss_coda":  ("A*exp(-(x-mu)**2/(2*s**2)) + T*exp((x-mu)/b + s**2/(2*b**2))"
                    "*erfc((x-mu)/(sqrt(2)*s) + s/(sqrt(2)*b)) + p0 + p1*(x-mu)",
                    "fotopicco con coda esponenziale a sinistra su fondo lineare"),
    "esponenziale": ("A*exp(-x/tau) + c", "decadimento / attenuazione"),
    "potenza":     ("a*x**b", "legge di potenza"),
    "risoluzione": ("sqrt(a + b*x + c*x**2)", "FWHM in funzione dell'energia"),
    "efficienza":  ("exp(a + b*log(x) + c*log(x)**2)", "efficienza vs energia (log-quadratica)"),
}

# Funzioni ammesse nella legge: solo queste vengono riconosciute come funzioni
_ALLOWED = {name: getattr(sp, name) for name in
            ("exp", "log", "sqrt", "sin", "cos", "tan", "sinh", "cosh", "tanh",
             "atan", "asin", "acos", "erf", "erfc", "Abs", "pi", "E")}
_ALLOWED.update({"abs": sp.Abs, "log10": lambda z: sp.log(z, 10), "ln": sp.log})


# --------------------------------------------------------------------------
# Lettura dati
# --------------------------------------------------------------------------
def read_columns(path):
    rows = []
    with open(path, errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            toks = [t for t in re.split(r"[\s,;]+", s) if t]
            try:
                rows.append([float(t) for t in toks])
            except ValueError:
                continue                     # intestazione o riga di testo
    if not rows:
        raise ValueError("nessuna riga numerica trovata")
    n = min(len(r) for r in rows)
    return np.array([r[:n] for r in rows])


def read_spe(path):
    """Legge un .Spe ASCII di MAESTRO: conteggi, live time e calibrazione."""
    with open(path, errors="ignore") as f:
        L = [l.strip() for l in f]
    counts, cal, ener, lt = None, None, None, None
    for i, l in enumerate(L):
        k = l.upper()
        if k.startswith("$DATA:"):
            a, b = map(int, L[i + 1].split()[:2])
            counts = np.array([float(L[i + 2 + j].split()[0]) for j in range(b - a + 1)])
        elif k.startswith("$MCA_CAL:"):
            n = int(L[i + 1].split()[0])
            cal = [float(t) for t in L[i + 2].split()[:n]]
        elif k.startswith("$ENER_FIT:"):
            ener = [float(t) for t in L[i + 1].split()[:2]]
        elif k.startswith("$MEAS_TIM:"):
            lt = float(L[i + 1].split()[0])
    if counts is None:
        raise ValueError("blocco $DATA non trovato")
    if not cal or not any(cal[1:]):
        cal = ener if ener and ener[1] else None
    return counts, cal, lt


# --------------------------------------------------------------------------
# Legge -> funzione numerica
# --------------------------------------------------------------------------
def parse_law(text, xname="x"):
    text = text.strip()
    if text in LEGGI:
        text = LEGGI[text][0]
    text = text.replace("^", "**")
    x = sp.Symbol(xname)
    # ogni nome che non è una funzione ammessa diventa un simbolo (parametro)
    names = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", text)) - set(_ALLOWED)
    local = dict(_ALLOWED)
    local.update({n: sp.Symbol(n) for n in names})
    try:
        expr = sp.sympify(text, locals=local)
    except (sp.SympifyError, SyntaxError, TypeError) as e:
        raise ValueError("legge non valida: controlla parentesi, operatori "
                         "(usa * per moltiplicare e ** o ^ per le potenze) e nomi delle funzioni")
    if x not in expr.free_symbols:
        raise ValueError(f"la legge non contiene la variabile {xname}")
    params = sorted((s for s in expr.free_symbols if s != x), key=lambda s: s.name)
    if not params:
        raise ValueError("la legge non ha parametri liberi")
    f = sp.lambdify([x] + params, expr, modules=["scipy", "numpy"])
    dfdx = sp.lambdify([x] + params, sp.diff(expr, x), modules=["scipy", "numpy"])
    return expr, [p.name for p in params], f, dfdx


def parse_kv(text):
    """'a=1, b=2e-3' -> {'a':1.0,'b':0.002}"""
    out = {}
    for part in filter(None, re.split(r"[,\s]+", text or "")):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = float(v)
    return out


def parse_bounds(text, names):
    """'a:0:inf, s:0:50' -> (lower, upper)"""
    lo = [-np.inf] * len(names); hi = [np.inf] * len(names)
    for part in filter(None, re.split(r"[,\s]+", text or "")):
        try:
            k, a, b = part.split(":")
            i = names.index(k)
        except ValueError:
            raise ValueError(f"limite non valido '{part}': usa nome:min:max con un parametro della legge")
        lo[i] = float(a) if a else -np.inf
        hi[i] = float(b) if b else np.inf
    return lo, hi


def guess_p0(names, x, y, user):
    """Valori iniziali: quelli dati dall'utente, altrimenti euristiche per i
    nomi tipici (A, mu, s, ...) o 1."""
    g = {}
    imax = int(np.argmax(y))
    for n in names:
        if n in user:
            g[n] = user[n]
        elif n in ("A", "amp", "N"):
            g[n] = float(y.max() - y.min()) or 1.0
        elif n in ("mu", "x0", "centroide"):
            g[n] = float(x[imax])
        elif n in ("s", "sigma", "sig"):
            g[n] = float((x.max() - x.min()) / 6) or 1.0
        elif n in ("tau",):
            g[n] = float((x.max() - x.min()) / 3) or 1.0
        elif n in ("c", "p0", "q"):
            g[n] = float(y.min())
        else:
            g[n] = 1.0
    return [g[n] for n in names]


# --------------------------------------------------------------------------
# Fit
# --------------------------------------------------------------------------
def _safe(f):
    """Rende la funzione robusta: valori non finiti (es. sqrt di un negativo
    durante l'iterazione) diventano grandi, cosi' l'ottimizzatore li evita."""
    def g(xx, *q):
        with np.errstate(all="ignore"):
            v = np.asarray(f(xx, *q), float) * np.ones_like(xx, dtype=float)
        return np.where(np.isfinite(v), v, 1e30)
    return g


def _multistart(fs, x, y, w, p0, bounds, fixed, n_try=400, seed=0):
    """Se il fit dai valori iniziali non converge, prova molti punti di
    partenza con ordini di grandezza casuali (da 1e-6 a 1e4, entrambi i segni)
    per i parametri non fissati dall'utente; restituisce il migliore."""
    rng = np.random.default_rng(seed)
    lo, hi = np.array(bounds[0], float), np.array(bounds[1], float)
    best, best_cost = None, np.inf
    for _ in range(n_try):
        q = np.array(p0, float)
        for i in range(len(q)):
            if i in fixed:
                continue
            v = 10 ** rng.uniform(-6, 4) * rng.choice([-1, 1])
            if lo[i] >= 0:
                v = abs(v)
            if hi[i] <= 0:
                v = -abs(v)
            q[i] = np.clip(v, lo[i] if np.isfinite(lo[i]) else -np.inf,
                           hi[i] if np.isfinite(hi[i]) else np.inf)
        r = (y - fs(x, *q)) * w
        cost = float(np.sum(r**2))
        if np.isfinite(cost) and cost < best_cost:
            best, best_cost = q, cost
    return best


def do_fit(f, dfdx, names, x, y, sy, sx, p0, bounds, fixed=(), max_iter=10):
    """Minimi quadrati pesati. Se ci sono incertezze su x usa il metodo della
    varianza efficace: sigma_eff^2 = sy^2 + (df/dx * sx)^2, iterato."""
    fs = _safe(f)
    weighted = sy is not None or sx is not None
    s_eff = (sy.copy() if sy is not None else np.ones_like(y)) if weighted else None
    p = np.array(p0, float)

    def fit_once(start, sig):
        return curve_fit(fs, x, y, p0=start, sigma=sig, absolute_sigma=weighted,
                         bounds=bounds, maxfev=20000)
    try:
        p_new, cov = fit_once(p, s_eff)
    except RuntimeError:
        w = 1 / s_eff if weighted else np.ones_like(y)
        start = _multistart(fs, x, y, w, p, bounds, set(fixed))
        if start is None:
            raise RuntimeError("nessun punto di partenza valido: fornisci valori iniziali")
        p_new, cov = fit_once(start, s_eff)
        print("  (convergenza ottenuta con ricerca multi-partenza dei valori iniziali)")
    p = p_new
    if sx is not None:
        for _ in range(max_iter):
            with np.errstate(all="ignore"):
                deriv = np.asarray(dfdx(x, *p), float) * np.ones_like(x)
            base = sy if sy is not None else 0.0
            s_eff = np.sqrt(base**2 + (deriv * sx) ** 2)
            s_eff = np.where(s_eff > 0, s_eff, np.min(s_eff[s_eff > 0]))
            p_new, cov = fit_once(p, s_eff)
            done = np.allclose(p_new, p, rtol=1e-8, atol=0)
            p = p_new
            if done:
                break
    yfit = fs(x, *p)
    res = y - yfit
    ndof = len(x) - len(p)
    out = {"p": p, "cov": cov, "perr": np.sqrt(np.diag(cov)), "ndof": ndof,
           "res": res, "yfit": yfit, "weighted": weighted, "s_eff": s_eff}
    if weighted:
        chi2 = float(np.sum((res / s_eff) ** 2))
        out.update(chi2=chi2, chi2r=chi2 / ndof if ndof > 0 else np.nan,
                   pval=float(stats.chi2.sf(chi2, ndof)) if ndof > 0 else np.nan)
    else:
        rss = float(np.sum(res**2))
        out.update(rss=rss, s_res=np.sqrt(rss / ndof) if ndof > 0 else np.nan)
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    out["R2"] = 1 - float(np.sum(res**2)) / ss_tot if ss_tot > 0 else np.nan
    return out


def derived(defs, names, R):
    """Grandezze funzione dei parametri, es. 'area=A*s*sqrt(2*pi)+2*b*T'.
    Incertezza per propagazione lineare con la matrice di covarianza
    completa: sigma^2 = g^T C g, con g gradiente rispetto ai parametri."""
    out = []
    syms = {n: sp.Symbol(n) for n in names}
    local = dict(_ALLOWED); local.update(syms)
    for part in filter(None, [d.strip() for d in re.split(r";", defs or "")]):
        label, text = part.split("=", 1) if "=" in part else (part, part)
        expr = sp.sympify(text.replace("^", "**"), locals=local)
        extra = expr.free_symbols - set(syms.values())
        if extra:
            raise ValueError(f"grandezza '{label.strip()}': simboli sconosciuti {extra}")
        args = [syms[n] for n in names]
        val = float(sp.lambdify(args, expr, modules=["scipy", "numpy"])(*R["p"]))
        g = np.array([float(sp.lambdify(args, sp.diff(expr, a), modules=["scipy", "numpy"])(*R["p"]))
                      for a in args])
        out.append((label.strip(), val, float(np.sqrt(g @ R["cov"] @ g))))
    return out


def fmt_val(v, e):
    """Valore ± incertezza con cifre significative coerenti (2 sull'errore)."""
    if not np.isfinite(e) or e == 0:
        return f"{v:.6g}"
    d = max(0, 1 - int(np.floor(np.log10(abs(e)))))
    if abs(v) >= 1e5 or (abs(v) < 1e-3 and v != 0):
        return f"{v:.3e} ± {e:.2e}"
    return f"{v:.{d}f} ± {e:.{d}f}"


def report(expr, names, R, xname, src, n):
    L = [f"Dati: {src}  ({n} punti)", f"Legge: y = {sp.sstr(expr)}", ""]
    L.append("Parametri:")
    for nm, v, e in zip(names, R["p"], R["perr"]):
        rel = f"  ({abs(e / v) * 100:.2g} %)" if v != 0 and np.isfinite(e) else ""
        L.append(f"  {nm:>10s} = {fmt_val(v, e)}{rel}")
    L.append("")
    if R["weighted"]:
        L.append(f"chi2 = {R['chi2']:.4g}   gradi di libertà = {R['ndof']}   "
                 f"chi2 ridotto = {R['chi2r']:.4g}   p-value = {R['pval']:.3g}")
        if R["ndof"] > 0:
            lo, hi = stats.chi2.ppf([0.025, 0.975], R["ndof"]) / R["ndof"]
            L.append(f"(intervallo atteso al 95% per il chi2 ridotto: {lo:.2f} – {hi:.2f})")
        L.append("Incertezze dei parametri dalle sigma dei dati (absolute_sigma).")
    else:
        L.append(f"Nessuna sigma sui dati: deviazione standard dei residui = {R['s_res']:.4g}")
        L.append("Incertezze dei parametri stimate dalla dispersione dei residui;")
        L.append("chi2 e p-value non sono calcolabili senza incertezze sui dati.")
    L.append(f"R^2 = {R['R2']:.6f}")
    if len(names) > 1:
        d = np.sqrt(np.diag(R["cov"]))
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = R["cov"] / np.outer(d, d)
        L.append("\nMatrice di correlazione:")
        L.append("           " + "".join(f"{nm:>9s}" for nm in names))
        for nm, row in zip(names, corr):
            L.append(f"  {nm:>8s} " + "".join(f"{c:9.3f}" for c in row))
    return "\n".join(L)


def plot(x, y, sy, sx, f, R, expr, names, xlabel, ylabel, logy, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1]})
    a1.errorbar(x, y, yerr=sy, xerr=sx, fmt="o", ms=3, lw=0.8, capsize=1.5, label="dati")
    xs = np.linspace(x.min(), x.max(), 800)
    with np.errstate(all="ignore"):
        ys = np.asarray(f(xs, *R["p"]), float) * np.ones_like(xs)
    a1.plot(xs, ys, "r-", lw=1.5,
            label="fit")
    txt = "\n".join(f"{n} = {fmt_val(v, e)}" for n, v, e in zip(names, R["p"], R["perr"]))
    if R["weighted"]:
        txt += f"\nχ²/ndf = {R['chi2']:.1f}/{R['ndof']}"
    a1.text(0.02, 0.97, txt, transform=a1.transAxes, va="top", fontsize=9,
            family="monospace", bbox=dict(fc="white", alpha=0.8, lw=0.5))
    import textwrap
    a1.set_title("\n".join(textwrap.wrap(f"y = {sp.sstr(expr)}", 95)), fontsize=9)
    a1.set_ylabel(ylabel); a1.legend(loc="upper right")
    if logy:
        a1.set_yscale("log")
    if R["weighted"]:
        a2.errorbar(x, R["res"] / R["s_eff"], yerr=1, fmt="o", ms=3, lw=0.8)
        a2.set_ylabel("residui / σ")
        a2.axhspan(-2, 2, color="0.9", zorder=0)
    else:
        a2.plot(x, R["res"], "o", ms=3)
        a2.set_ylabel("residui")
    a2.axhline(0, color="r", lw=1)
    a2.set_xlabel(xlabel)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


# --------------------------------------------------------------------------
# Caricamento dati (CLI o interattivo)
# --------------------------------------------------------------------------
def ask(prompt, default=None):
    s = input(f"{prompt}" + (f" [{default}]" if default not in (None, "") else "") + ": ").strip()
    return s if s else (default if default is not None else "")


def load_data(a, interactive):
    """Restituisce x, y, sy, sx, etichette, descrizione della sorgente."""
    path = a.file
    if interactive and not path:
        path = ask("File di dati (.csv/.txt/.Spe), oppure invio per inserirli a mano")
    if not path:
        print("Inserisci una riga per punto: x y [sigma_y [sigma_x]]. Riga vuota per finire.")
        rows = []
        while True:
            s = input("> ").strip()
            if not s:
                break
            try:
                rows.append([float(t) for t in re.split(r"[\s,;]+", s) if t])
            except ValueError:
                print("  riga ignorata: servono numeri")
        if len(rows) < 2:
            raise ValueError("servono almeno due punti")
        n = min(len(r) for r in rows)
        arr = np.array([r[:n] for r in rows])
        sy = arr[:, 2] if n > 2 else None
        sx = arr[:, 3] if n > 3 else None
        return arr[:, 0], arr[:, 1], sy, sx, "x", "y", "dati inseriti a mano"

    if path.lower().endswith(".spe"):
        counts, cal, lt = read_spe(path)
        ch = np.arange(len(counts), dtype=float)
        use_e = cal is not None and not a.channels
        xv = sum(c * ch**k for k, c in enumerate(cal)) if use_e else ch
        rng = a.range
        if interactive and rng is None:
            r = ask(f"Intervallo in {'keV' if use_e else 'canali'} (min max), invio per tutto", "")
            rng = [float(v) for v in r.split()] if r else None
        m = np.ones(len(ch), bool) if rng is None else (xv >= rng[0]) & (xv <= rng[1])
        y = counts[m]
        sy = np.sqrt(np.clip(y, 1, None))        # Poisson; 1 per i canali vuoti
        return (xv[m], y, sy, None, "Energia [keV]" if use_e else "Canale", "Conteggi",
                f"{os.path.basename(path)}" + (f" [{rng[0]:g}, {rng[1]:g}]" if rng else ""))

    arr = read_columns(path)
    print(f"Lette {arr.shape[0]} righe e {arr.shape[1]} colonne da {path}")
    if interactive and a.y is None:
        print("Prime righe:\n" + "\n".join("  " + "  ".join(f"{v:g}" for v in r) for r in arr[:3]))
        a.x = int(ask("Colonna di x (da 0)", 0))
        a.y = int(ask("Colonna di y", 1))
        s = ask("Colonna di sigma_y (invio se assente, 'poisson' per sqrt(y))", "")
        a.sy = None if s == "" else s
        s = ask("Colonna di sigma_x (invio se assente)", "")
        a.sx = None if s == "" else s
    xi = a.x if a.x is not None else 0
    yi = a.y if a.y is not None else 1
    x, y = arr[:, xi], arr[:, yi]
    if a.sy is None:
        sy = None
    elif str(a.sy).lower() == "poisson":
        sy = np.sqrt(np.clip(y, 1, None))
    else:
        sy = arr[:, int(a.sy)]
    sx = None if a.sx is None else arr[:, int(a.sx)]
    if a.range:
        m = (x >= a.range[0]) & (x <= a.range[1])
        x, y = x[m], y[m]
        sy = sy[m] if sy is not None else None
        sx = sx[m] if sx is not None else None
    return x, y, sy, sx, a.xlabel or "x", a.ylabel or "y", os.path.basename(path)


def run_fit(law, p0_text, bounds_text, x, y, sy, sx, labels, src, outdir, tag, logy,
            der_text=""):
    expr, names, f, dfdx = parse_law(law)
    user = parse_kv(p0_text)
    unknown = set(user) - set(names)
    if unknown:
        raise ValueError(f"parametri non presenti nella legge: {', '.join(sorted(unknown))}")
    p0 = guess_p0(names, x, y, user)
    bounds = parse_bounds(bounds_text, names)
    p0 = [min(max(v, lo), hi) for v, lo, hi in zip(p0, *bounds)]
    if sy is not None and np.any(sy <= 0):
        raise ValueError("ci sono sigma_y nulle o negative")
    fixed = [i for i, n in enumerate(names) if n in user]
    R = do_fit(f, dfdx, names, x, y, sy, sx, p0, bounds, fixed)
    txt = report(expr, names, R, "x", src, len(x))
    if der_text:
        D = derived(der_text, names, R)
        txt += "\n\nGrandezze derivate (propagazione con covarianza completa):\n" + "\n".join(
            f"  {lb:>10s} = {fmt_val(v, e)}" + (f"  ({abs(e / v) * 100:.2g} %)" if v else "")
            for lb, v, e in D)
    print("\n" + txt + "\n")
    os.makedirs(outdir, exist_ok=True)
    base = os.path.join(outdir, tag)
    with open(base + "_report.txt", "w") as fh:
        fh.write(txt + "\n")
    cols = [x, y] + ([sy] if sy is not None else []) + [R["yfit"], R["res"]]
    hdr = "x,y" + (",sigma_y" if sy is not None else "") + ",y_fit,residuo"
    np.savetxt(base + "_fit.csv", np.column_stack(cols), delimiter=",", header=hdr,
               comments="", fmt="%.8g")
    plot(x, y, sy, sx, f, R, expr, names, labels[0], labels[1], logy, base + "_fit.png")
    print(f"Salvati: {base}_report.txt, {base}_fit.csv, {base}_fit.png")
    return R


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="file di dati (.csv/.txt/.dat/.Spe)")
    ap.add_argument("--x", type=int, help="colonna di x (da 0)")
    ap.add_argument("--y", type=int, help="colonna di y")
    ap.add_argument("--sy", help="colonna di sigma_y, oppure 'poisson'")
    ap.add_argument("--sx", help="colonna di sigma_x")
    ap.add_argument("--range", type=float, nargs=2, metavar=("MIN", "MAX"),
                    help="intervallo di x da fittare")
    ap.add_argument("--channels", action="store_true", help=".Spe: usa i canali anche se calibrato")
    ap.add_argument("--legge", help="espressione in x oppure nome di una legge predefinita")
    ap.add_argument("--p0", default="", help="valori iniziali, es. 'a=1,b=0.5'")
    ap.add_argument("--bounds", default="", help="limiti, es. 's:0:,A:0:1e6'")
    ap.add_argument("--derivate", default="",
                    help="grandezze dai parametri, separate da ';', es. 'area=A*s*sqrt(2*pi)'")
    ap.add_argument("--xlabel"); ap.add_argument("--ylabel")
    ap.add_argument("--logy", action="store_true")
    ap.add_argument("--outdir", default="fit_out")
    ap.add_argument("--tag", default="fit", help="prefisso dei file di uscita")
    a = ap.parse_args()
    interactive = a.legge is None

    try:
        x, y, sy, sx, xl, yl, src = load_data(a, interactive)
    except (OSError, ValueError) as e:
        sys.exit(f"Errore nei dati: {e}")
    if len(x) < 2:
        sys.exit("Errore nei dati: meno di due punti nell'intervallo scelto")
    print(f"{len(x)} punti, x in [{x.min():g}, {x.max():g}]"
          + ("" if sy is not None else "  (nessuna incertezza su y)"))

    if not interactive:
        try:
            run_fit(a.legge, a.p0, a.bounds, x, y, sy, sx, (xl, yl), src,
                    a.outdir, a.tag, a.logy, a.derivate)
        except Exception as e:
            sys.exit(f"Fit non riuscito: {e}")
        return

    print("\nScrivi la legge in funzione di x (es. a*exp(-b*x)+c).")
    print("Comandi: 'leggi' elenca le leggi pronte, 'q' esce.")
    k = 0
    while True:
        law = ask("\nLegge")
        if law.lower() in ("q", "quit", "esci", ""):
            break
        if law.lower() == "leggi":
            for nm, (ex, d) in LEGGI.items():
                print(f"  {nm:<13s} {ex:<45s} {d}")
            continue
        try:
            _, names, _, _ = parse_law(law)
        except ValueError as e:
            print(f"  {e}")
            continue
        print(f"  Parametri trovati: {', '.join(names)}")
        p0 = ask("  Valori iniziali (es. " + ", ".join(f"{n}=1" for n in names[:2])
                 + "), invio per automatici", "")
        bnd = ask("  Limiti (es. " + f"{names[0]}:0:" + "), invio per nessuno", "")
        der = ask("  Grandezze derivate (es. area=A*s*sqrt(2*pi)), invio per nessuna", "")
        k += 1
        try:
            run_fit(law, p0, bnd, x, y, sy, sx, (xl, yl), src, a.outdir,
                    f"{a.tag}{k}", a.logy, der)
        except Exception as e:
            print(f"  Fit non riuscito: {e}\n  Prova a cambiare i valori iniziali o i limiti.")


if __name__ == "__main__":
    main()
