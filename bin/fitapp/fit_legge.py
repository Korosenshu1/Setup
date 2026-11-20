#!/usr/bin/env python3
"""
fit_legge.py - Fit ai minimi quadrati di dati con una legge scritta dall'utente.

Dati in ingresso:
  - file di testo/CSV a colonne. Il separatore (spazi, tab, virgola, punto e
    virgola) e la virgola decimale (es. "1,5;2,3" dei CSV in italiano) sono
    riconosciuti automaticamente; le righe di testo (intestazioni) e i
    commenti (#, %, //, !) vengono ignorati; celle vuote, "nan" o "-" sono
    dati mancanti e i punti corrispondenti vengono esclusi;
  - spettri MAESTRO .Spe (x = canale o energia se calibrato, y = conteggi,
    sigma = sqrt(conteggi)), con selezione dell'intervallo;
  - dati inseriti a mano nel terminale.

Legge: qualunque espressione in x, ad es.
    a*exp(-b*x) + c
    A*exp(-(x-mu)**2/(2*s**2)) + p0 + p1*x
    sqrt(a + b*x + c*x**2)
Sono disponibili exp, log, log10, sqrt, sin, cos, tan, erf, erfc, gamma,
sign, Heaviside, abs, pi ecc. I parametri sono riconosciuti automaticamente
(tutti i nomi diversi da x, anche parole riservate di Python come lambda).
Sono anche pronte alcune leggi con nome: digita "leggi" nel prompt.

Incertezze (--sy, --sx): numero di colonna (da 0), 'poisson', 'nessuna',
il nome di una formula del menu degli errori, oppure una formula in x, y e
nelle colonne c0, c1, ... (o nei loro nomi d'intestazione), ad es.
    "0.05*y"   "sqrt(c2**2 + (0.01*y)**2)"   "max(sqrt(y), 1)"   "0.5"
Un numero intero da solo indica una colonna: per un errore costante scrivi
ad es. "2.0".

Le leggi e le formule degli errori aggiunte dall'interfaccia grafica
(leggi_utente.json ed errori_utente.json, accanto a questo file) valgono
anche qui.

Uso interattivo:        python fit_legge.py
Uso da riga di comando: python fit_legge.py dati.csv --x 0 --y 1 --sy 2 \
                            --legge "a + b*x + c*x**2" --p0 "a=0,b=1,c=0"
                        python fit_legge.py cesio137.Spe --range 340 440 \
                            --legge gauss_lin --p0 "A=1e4,mu=388,s=13"

Grandezze derivate: --derivate "area=A*s*sqrt(2*pi)+2*b*T; fwhm=2.3548*s"
calcola funzioni dei parametri con incertezza propagata dalla covarianza.

--relativo: le sigma sono solo pesi relativi (es. errori stimati a occhio);
le incertezze dei parametri vengono scalate con sqrt(chi2 ridotto).

Uscite (cartella --outdir): grafico con residui (.png), report (.txt),
curva fittata e residui (.csv).

Riprodurre un fit: il report salvato contiene in fondo tutte le impostazioni
(file, colonne o asse, intervallo, formule delle sigma, legge, valori
iniziali, limiti, parametri fissati, grandezze derivate) e i risultati.
    python fit_legge.py --da-report fit_out/fit_report.txt --outdir rifatto
rifa' lo stesso fit (il file dei dati va lasciato dov'era o messo nella
cartella del report) e lo confronta con i risultati registrati. Lo stesso si
fa dalla GUI con "Riapri da report...". --fissi "p1=0" fissa dei parametri.
"""
import argparse
import ast
import hashlib
import json
import keyword
import os
import re
import sys
import warnings
from collections import Counter

import numpy as np
import sympy as sp
from scipy import stats
from scipy.optimize import curve_fit

CARTELLA = os.path.dirname(os.path.abspath(__file__))
FILE_LEGGI = os.path.join(CARTELLA, "leggi_utente.json")
FILE_ERRORI = os.path.join(CARTELLA, "errori_utente.json")

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

# Formule predefinite per le incertezze (variabili: x, y, colonne c0, c1, ...)
FORMULA_POISSON = "sqrt(max(y, 1))"
ERRORI = {
    "poisson √y":          (FORMULA_POISSON, "conteggi: errore poissoniano (1 per i valori nulli)"),
    "relativo 1%":         ("0.01*abs(y)", "1% del valore: cambia 0.01 per un'altra percentuale"),
    "risoluzione/√12":     ("0.01/sqrt(12)",
                            "lettura con risoluzione 0.01 (distribuzione uniforme): cambia 0.01"),
    "relativo + assoluto": ("sqrt((0.01*y)**2 + 0.01**2)",
                            "1% del valore e 0.01 assoluto sommati in quadratura"),
}
PREDEFINITE_LEGGI = dict(LEGGI)
PREDEFINITE_ERRORI = dict(ERRORI)

# Funzioni ammesse nella legge: solo queste vengono riconosciute come funzioni
_ALLOWED = {name: getattr(sp, name) for name in
            ("exp", "log", "sqrt", "sin", "cos", "tan", "sinh", "cosh", "tanh",
             "atan", "asin", "acos", "atan2", "erf", "erfc", "gamma", "sign",
             "Heaviside", "Abs", "pi")}
_ALLOWED.update({"abs": sp.Abs, "log10": lambda z: sp.log(z, 10), "ln": sp.log,
                 "heaviside": sp.Heaviside})
_COSTANTI = {"pi"}
# un nome non preceduto da cifre o punto (cosi' la "e" di 1e-3 non conta)
_RE_NOME = re.compile(r"(?<![\w.])[A-Za-z_]\w*")


# --------------------------------------------------------------------------
# Menu di leggi e formule degli errori salvati su file
# --------------------------------------------------------------------------
def carica_menu(path, predefinite, chiave):
    """Voci da un file JSON {nome: {chiave: testo, "descrizione": ...}}.
    Restituisce (voci, avviso); avviso e' None se tutto e' andato bene."""
    nome_file = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as f:
            dati = json.load(f)
    except FileNotFoundError:
        return dict(predefinite), None
    except (OSError, ValueError) as e:
        return dict(predefinite), f"{nome_file} non leggibile ({e})"
    if not isinstance(dati, dict):
        return dict(predefinite), f"{nome_file} non ha il formato atteso"
    voci = {}
    for nome, v in dati.items():
        if isinstance(v, dict) and isinstance(v.get(chiave), str):
            voci[str(nome)] = (v[chiave], str(v.get("descrizione", "")))
    return voci, None


def salva_menu(voci, path, chiave):
    """Scrive le voci nel file JSON (prima su un file temporaneo, cosi' un
    errore a meta' scrittura non rovina il file esistente)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({n: {chiave: t, "descrizione": d} for n, (t, d) in voci.items()},
                  f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def imposta_menu(menu, voci):
    """Sostituisce il contenuto del dizionario senza cambiarne l'identita'."""
    menu.clear()
    menu.update(voci)


def carica_menu_utente():
    """Carica leggi e formule degli errori salvate; restituisce gli avvisi."""
    avvisi = []
    for menu, path, pred, chiave in ((LEGGI, FILE_LEGGI, PREDEFINITE_LEGGI, "legge"),
                                     (ERRORI, FILE_ERRORI, PREDEFINITE_ERRORI, "formula")):
        voci, avviso = carica_menu(path, pred, chiave)
        imposta_menu(menu, voci)
        if avviso:
            avvisi.append(avviso)
    return avvisi


def menu_con(menu, nome, testo, descr, vecchio=None):
    """Nuovo dizionario con la voce aggiunta o sostituita. Se vecchio e' dato
    (modifica, anche con cambio di nome) la voce resta al suo posto; un'altra
    voce con lo stesso nome nuovo viene sostituita."""
    voce = (testo, descr)
    posto = vecchio if vecchio in menu else nome
    nuove = {}
    for k, v in menu.items():
        if k == posto:
            nuove[nome] = voce
        elif k != nome:
            nuove[k] = v
    if nome not in nuove:
        nuove[nome] = voce
    return nuove


# --------------------------------------------------------------------------
# Lettura dati
# --------------------------------------------------------------------------
_COMMENTI = ("#", "%", "//", "!")
_RE_NUM = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")
_RE_NUM_VIRG = re.compile(r"[+-]?\d*,\d+([eE][+-]?\d+)?")
_RE_RIGA_NUM = re.compile(r"[0-9eE+\-.,;\s]+")
_MANCANTI = {"", "nan", "na", "n/a", "-", "--", "?", "null", "none"}
SEPARATORI = {";": "punto e virgola", "\t": "tab", ",": "virgola", None: "spazi"}


def _sembra_numerica(s):
    t = re.sub(r"(?i)\bnan\b", "0", s)
    return bool(_RE_RIGA_NUM.fullmatch(t)) and any(c.isdigit() for c in t)


def _separatore(campione):
    """Dalle righe numeriche: (separatore, virgola_decimale)."""
    if any(";" in s for s in campione):
        return ";", True
    if any("\t" in s for s in campione):
        return "\t", any(_RE_NUM_VIRG.fullmatch(t.strip())
                         for s in campione for t in s.split("\t"))
    if any("," in s for s in campione):
        # "1,5 2,3": colonne separate da spazi con la virgola decimale
        righe = [s.split() for s in campione]
        if (all(len(r) >= 2 for r in righe) and len({len(r) for r in righe}) == 1
                and all(_RE_NUM.fullmatch(t) or _RE_NUM_VIRG.fullmatch(t) or t.lower() == "nan"
                        for r in righe for t in r)
                and any("," in t for r in righe for t in r)):
            return None, True
        return ",", False
    return None, False


def _numero(t, virgola):
    t = t.strip().strip("\"'").strip()
    if t.lower() in _MANCANTI:
        return np.nan
    if virgola:
        t = t.replace(",", ".")
    return float(t)


def read_table(path):
    """Legge un file a colonne. Restituisce un dizionario con:
    arr (righe x colonne, NaN per i dati mancanti), nomi (dall'intestazione
    o None), sep, virgola (decimale), scartate (righe con un numero di colonne
    diverso, non recuperabili), completate (righe corte riempite con NaN)."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        grezze = f.read().splitlines()
    righe_txt = []                               # (testo, e' un commento con #)
    for g in grezze:
        s = g.strip().lstrip("﻿").strip()
        if not s:
            continue
        if s.startswith("#"):
            righe_txt.append((s.lstrip("#").strip(), True))
            continue
        if s.startswith(_COMMENTI):
            continue
        if "#" in s:                             # commento in fondo alla riga
            s = s.split("#", 1)[0].strip()
        if s:
            righe_txt.append((s, False))
    campione = [s for s, c in righe_txt if not c and _sembra_numerica(s)][:500]
    if not campione:
        raise ValueError("nessuna riga numerica trovata")
    sep, virg = _separatore(campione)

    def dividi(s):
        toks = s.split() if sep is None else [t.strip() for t in s.split(sep)]
        while len(toks) > 1 and toks[-1] == "":      # separatore finale
            toks.pop()
        return toks

    righe, intest = [], None
    for s, commento in righe_txt:
        toks = dividi(s)
        if commento:
            if not righe and s and not _sembra_numerica(s):
                intest = toks
            continue
        try:
            v = [_numero(t, virg) for t in toks]
        except ValueError:
            if not righe:
                intest = toks                    # ultima riga di testo prima dei dati
            continue
        if all(np.isnan(v)):
            continue
        righe.append(v)
    if not righe:
        raise ValueError("nessuna riga numerica trovata")
    conta = Counter(len(r) for r in righe)
    n = max(conta.items(), key=lambda kv: (kv[1], kv[0]))[0]
    tenute, scartate, completate = [], 0, 0
    for r in righe:
        if len(r) == n:
            tenute.append(r)
        elif sep is not None and len(r) < n:     # celle finali vuote
            tenute.append(r + [np.nan] * (n - len(r)))
            completate += 1
        else:                                    # non si sa a che colonne corrispondono
            scartate += 1
    nomi = None
    if intest and len(intest) == n:
        nomi = [t.strip().strip("\"'").strip() or f"col{i}" for i, t in enumerate(intest)]
    return {"arr": np.array(tenute, float), "nomi": nomi, "sep": sep, "virgola": virg,
            "scartate": scartate, "completate": completate}


def read_columns(path):
    return read_table(path)["arr"]


def read_spe_full(path):
    """Legge un .Spe ASCII di MAESTRO. Restituisce un dizionario con counts,
    cal (coefficienti del polinomio canale -> energia, o None), lt e rt
    (live e real time, o None), primo (numero del primo canale), unita."""
    with open(path, encoding="utf-8", errors="replace") as f:
        L = [l.strip() for l in f]
    out = {"counts": None, "cal": None, "lt": None, "rt": None, "primo": 0, "unita": "keV"}
    ener = None
    for i, l in enumerate(L):
        k = l.upper()
        try:
            if k.startswith("$DATA:"):
                a, b = map(int, L[i + 1].split()[:2])
                n = b - a + 1
                vals = []
                for riga in L[i + 2:]:
                    if riga.startswith("$"):
                        break
                    vals.extend(float(t) for t in riga.split())
                    if len(vals) >= n:
                        break
                if len(vals) < n:
                    raise ValueError(f"incompleto: {len(vals)} canali su {n}")
                out["counts"], out["primo"] = np.array(vals[:n]), a
            elif k.startswith("$MCA_CAL:"):
                n = int(L[i + 1].split()[0])
                toks = L[i + 2].split()
                out["cal"] = [float(t) for t in toks[:n]]
                if len(toks) > n and not _RE_NUM.fullmatch(toks[n]):
                    out["unita"] = toks[n]
            elif k.startswith("$ENER_FIT:"):
                ener = [float(t) for t in L[i + 1].split()[:2]]
            elif k.startswith("$MEAS_TIM:"):
                t = L[i + 1].split()
                out["lt"] = float(t[0])
                out["rt"] = float(t[1]) if len(t) > 1 else None
        except (IndexError, ValueError) as e:
            if k.startswith("$DATA:"):
                raise ValueError(f"blocco $DATA non leggibile ({e})")
            # gli altri blocchi malformati si ignorano
    if out["counts"] is None:
        raise ValueError("blocco $DATA non trovato")
    cal = out["cal"]
    if not cal or not any(cal[1:]):
        out["cal"] = ener if ener and ener[1] else None
    return out


def read_spe(path):
    """Compatibilita': (conteggi, calibrazione, live time)."""
    d = read_spe_full(path)
    return d["counts"], d["cal"], d["lt"]


# --------------------------------------------------------------------------
# Formule delle incertezze
# --------------------------------------------------------------------------
FUNZ_ERRORI = {"sqrt": np.sqrt, "exp": np.exp, "log": np.log, "ln": np.log,
               "log10": np.log10, "abs": np.abs, "sin": np.sin, "cos": np.cos,
               "tan": np.tan, "max": np.maximum, "min": np.minimum, "pi": np.pi}
_NODI_OK = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load,
            ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
            ast.USub, ast.UAdd)


def compila_formula(testo):
    """Controlla la formula di un'incertezza. Restituisce (codice, nomi usati)."""
    t = (testo or "").strip().replace("^", "**")
    if not t:
        raise ValueError("formula vuota")
    try:
        albero = ast.parse(t, mode="eval")
    except SyntaxError:
        if re.search(r"\d,\d", t):
            raise ValueError("formula non valida: usa il punto decimale (0.05, non 0,05)")
        raise ValueError("formula non valida: controlla parentesi e operatori "
                         "(usa * per moltiplicare e il punto come separatore decimale)")
    nomi = set()
    for n in ast.walk(albero):
        if isinstance(n, ast.Tuple):
            raise ValueError("formula non valida: usa il punto decimale (0.05, non 0,05)")
        if not isinstance(n, _NODI_OK):
            raise ValueError(f"formula non valida: '{ast.get_source_segment(t, n) or type(n).__name__}'"
                             " non è ammesso")
        if isinstance(n, ast.Call):
            if (not isinstance(n.func, ast.Name) or n.func.id not in FUNZ_ERRORI
                    or n.func.id == "pi" or n.keywords):
                nome = getattr(n.func, "id", "?")
                raise ValueError(f"'{nome}' non è una funzione disponibile nelle formule "
                                 f"(disponibili: {', '.join(k for k in FUNZ_ERRORI if k != 'pi')})")
        elif isinstance(n, ast.Constant) and not isinstance(n.value, (int, float)):
            raise ValueError("formula non valida: sono ammessi solo numeri, variabili e funzioni")
        elif isinstance(n, ast.Name) and n.id not in FUNZ_ERRORI:
            nomi.add(n.id)
    return compile(albero, "<formula>", "eval"), nomi


def valuta_formula(testo, variabili, n):
    """Valuta la formula sui dati; restituisce un array lungo n."""
    codice, nomi = compila_formula(testo)
    ignoti = nomi - set(variabili)
    if ignoti:
        raise ValueError(f"nomi sconosciuti nella formula: {', '.join(sorted(ignoti))} "
                         f"(disponibili: {', '.join(variabili)})")
    ambiente = {"__builtins__": {}}
    ambiente.update(FUNZ_ERRORI)
    ambiente.update(variabili)
    try:
        with np.errstate(all="ignore"):
            v = np.asarray(eval(codice, ambiente), float)
    except (TypeError, ValueError, ArithmeticError) as e:
        raise ValueError(f"formula non valutabile: {e}")
    try:
        return np.broadcast_to(v, (n,)).astype(float)
    except ValueError:
        raise ValueError("la formula non dà un valore per ogni punto")


def variabili_tabella(arr, nomi, x, y):
    """Variabili utilizzabili nelle formule: x, y, c0, c1, ... e i nomi
    d'intestazione che sono identificatori validi."""
    v = {"x": x, "y": y}
    for i in range(arr.shape[1]):
        v[f"c{i}"] = arr[:, i]
    for i, nm in enumerate(nomi or []):
        if (nm.isidentifier() and not keyword.iskeyword(nm) and nm not in v
                and nm not in FUNZ_ERRORI):
            v[nm] = arr[:, i]
    return v


def formula_errore(s):
    """Nome del menu o 'poisson' -> formula; altrimenti il testo stesso."""
    s = s.strip()
    if s in ERRORI:
        return ERRORI[s][0]
    if s.lower() == "poisson":
        return FORMULA_POISSON
    return s


def risolvi_sigma(spec, variabili, n, arr=None):
    """spec: None/'nessuna', numero intero di colonna (se arr e' dato),
    'poisson', nome di una formula del menu, oppure una formula."""
    if spec is None:
        return None
    s = str(spec).strip()
    if s.lower() in ("", "nessuna", "none", "no"):
        return None
    if arr is not None and re.fullmatch(r"\d+", s):
        i = int(s)
        if i >= arr.shape[1]:
            raise ValueError(f"colonna {i} inesistente (il file ha {arr.shape[1]} colonne, da 0)")
        return arr[:, i].astype(float)
    return valuta_formula(formula_errore(s), variabili, n)


def punti_validi(*arrays):
    """Maschera dei punti in cui tutti gli array dati (non None) sono finiti."""
    m = None
    for a in arrays:
        if a is None:
            continue
        ok = np.isfinite(np.asarray(a, float))
        m = ok if m is None else m & ok
    return m


def controlla_sigma(sy, sx, x):
    """Errori chiari per sigma non utilizzabili nel fit."""
    if sy is not None:
        bad = ~(sy > 0)
        if bad.any():
            i = int(np.flatnonzero(bad)[0])
            raise ValueError(f"{int(bad.sum())} punti con σ y nulla o negativa (il primo a "
                             f"x = {x[i]:g}). Con una formula puoi imporre un minimo, es. "
                             "max(0.01*abs(y), 0.1), oppure restringi l'intervallo")
    if sx is not None and np.any(sx < 0):
        raise ValueError("ci sono σ x negative")


# --------------------------------------------------------------------------
# Legge -> funzione numerica
# --------------------------------------------------------------------------
def _sympifica(text):
    """Testo -> espressione sympy. Ogni nome che non e' una funzione ammessa
    diventa un simbolo, anche se e' una parola riservata di Python (lambda)."""
    text = (text or "").strip().replace("^", "**")
    if not text:
        raise ValueError("espressione vuota")
    for m in re.finditer(r"(?<![\w.])([A-Za-z_]\w*)\s*\(", text):
        nm = m.group(1)
        if nm not in _ALLOWED or nm in _COSTANTI:
            raise ValueError(f"'{nm}' è usato come funzione ma non è tra quelle disponibili; "
                             "se è un parametro, metti * prima della parentesi")
    local = dict(_ALLOWED)
    for nm in set(_RE_NOME.findall(text)) - set(_ALLOWED):
        if keyword.iskeyword(nm):
            alias = f"KW_{nm}_"
            text = re.sub(rf"(?<![\w.]){nm}\b", alias, text)
            local[alias] = sp.Symbol(nm)
        else:
            local[nm] = sp.Symbol(nm)
    try:
        expr = sp.sympify(text, locals=local)
    except Exception:
        expr = None
    if not isinstance(expr, sp.Expr):
        raise ValueError("espressione non valida: controlla parentesi, operatori (usa * per "
                         "moltiplicare, ** o ^ per le potenze, il punto come separatore "
                         "decimale) e nomi delle funzioni")
    return expr


def parse_law(text, xname="x"):
    text = text.strip()
    if text in LEGGI:
        text = LEGGI[text][0]
    try:
        expr = _sympifica(text)
    except ValueError as e:
        raise ValueError(str(e).replace("espressione", "legge", 1))
    x = sp.Symbol(xname)
    if x not in expr.free_symbols:
        raise ValueError(f"la legge non contiene la variabile {xname}")
    params = sorted((s for s in expr.free_symbols if s != x), key=lambda s: s.name)
    if not params:
        raise ValueError("la legge non ha parametri liberi")
    # dummify: argomenti con nomi sicuri anche per parametri come 'lambda'
    f = sp.lambdify([x] + params, expr, modules=["scipy", "numpy"], dummify=True)
    dfdx = sp.lambdify([x] + params, sp.diff(expr, x), modules=["scipy", "numpy"],
                       dummify=True)
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
    nomi tipici (A, mu, s, ...) o 1. Se il fit da questi valori va male,
    do_fit prova da solo molti altri punti di partenza."""
    g = {}
    imax = int(np.argmax(y))
    for n in names:
        if n in user:
            g[n] = user[n]
        elif n in ("A", "amp", "N"):
            g[n] = float(y.max() - y.min()) or 1.0
        elif n in ("mu", "x0", "xc", "centroide"):
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


def dentro_limiti(p0, lo, hi):
    return [min(max(float(v), a), b) for v, a, b in zip(p0, lo, hi)]


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


def valuta_curva(f, xs, p):
    """Curva per i grafici: i valori non finiti diventano NaN (buchi)."""
    xs = np.asarray(xs, float)
    with np.errstate(all="ignore"):
        try:
            v = np.asarray(f(xs, *p), float) * np.ones_like(xs)
        except (TypeError, ValueError, ZeroDivisionError, OverflowError):
            return np.full_like(xs, np.nan)
    return np.where(np.isfinite(v), v, np.nan)


def _scale_dati(x, y):
    """Valori tipici dei dati, buoni candidati per parametri di posizione
    (centroidi, soglie), larghezza, ampiezza e fondo."""
    ix, iy = int(np.argmax(y)), int(np.argmin(y))
    dx, dy = float(np.ptp(x)) or 1.0, float(np.ptp(y)) or 1.0
    v = [x[ix], x[iy], np.median(x), x.min(), x.max(), dx / 20, dx / 6, dx / 2, dx,
         y.max(), y.min(), dy, np.mean(y), 1.0]
    v = [float(t) for t in v if np.isfinite(t) and t != 0]
    return v + [-t for t in v]


def _partenze(fs, x, y, w, p0, bounds, fixed, n_try=1500, n_best=8, seed=0):
    """Punti di partenza casuali per i parametri non dati dall'utente: dentro
    i limiti se sono finiti, altrimenti per lo piu' valori tipici dei dati
    (posizione del massimo, ampiezza dell'intervallo, escursione di y, ...)
    moltiplicati per un fattore casuale, o ordini di grandezza casuali (da
    1e-6 a 100 volte la scala dei dati, entrambi i segni). Restituisce i
    migliori n_best per somma dei quadrati dei residui."""
    rng = np.random.default_rng(seed)
    lo, hi = np.array(bounds[0], float), np.array(bounds[1], float)
    with np.errstate(all="ignore"):
        scala = float(np.nanmax(np.abs(np.concatenate([x, y]))))
    e_max = max(4.0, np.log10(scala) + 2) if np.isfinite(scala) and scala > 0 else 4.0
    tipici = _scale_dati(x, y)
    cand = []
    for _ in range(n_try):
        q = np.array(p0, float)
        for i in range(len(q)):
            if i in fixed:
                continue
            if np.isfinite(lo[i]) and np.isfinite(hi[i]):
                v = rng.uniform(lo[i], hi[i])
            elif rng.random() < 0.7:
                v = tipici[rng.integers(len(tipici))] * 10 ** rng.uniform(-0.3, 0.3)
                v = min(max(v, lo[i]), hi[i])
            else:
                v = 10 ** rng.uniform(-6, e_max) * rng.choice([-1, 1])
                if lo[i] >= 0:
                    v = abs(v)
                if hi[i] <= 0:
                    v = -abs(v)
                v = min(max(v, lo[i]), hi[i])
            q[i] = v
        cost = float(np.sum(((y - fs(x, *q)) * w) ** 2))
        if np.isfinite(cost):
            cand.append((cost, q))
    cand.sort(key=lambda t: t[0])
    return [q for _, q in cand[:n_best]]


def do_fit(f, dfdx, names, x, y, sy, sx, p0, bounds, fixed=(), max_iter=10, relativo=False):
    """Minimi quadrati pesati. Se ci sono incertezze su x usa il metodo della
    varianza efficace: sigma_eff^2 = sy^2 + (df/dx * sx)^2, iterato.
    fixed: indici dei parametri con valore iniziale dato dall'utente (non
    vengono cambiati nella ricerca multi-partenza).
    relativo: le sigma sono pesi relativi; la covarianza e' scalata col chi2."""
    fs = _safe(f)
    weighted = sy is not None or sx is not None
    s_eff = (sy.copy() if sy is not None else np.ones_like(y)) if weighted else None
    lo, hi = list(bounds[0]), list(bounds[1])
    p0 = dentro_limiti(p0, lo, hi)
    assoluto = weighted and not relativo
    note = []
    ndof = len(x) - len(p0)

    def fit_once(start, sig):
        return curve_fit(fs, x, y, p0=start, sigma=sig, absolute_sigma=assoluto,
                         bounds=(lo, hi), maxfev=20000)

    def costo(p, sig):
        r = y - fs(x, *p)
        if sig is not None:
            r = r / sig
        return float(np.sum(r ** 2))

    def cattivo(c, sig):
        if ndof <= 0:
            return False
        if sig is not None and assoluto:
            return c / ndof > 4
        rif = costo_costante(sig)
        return rif > 0 and c > 0.25 * rif         # spiega meno del 75% della varianza

    def costo_costante(sig):
        w = np.ones_like(y) if sig is None else 1 / sig ** 2
        m = np.sum(w * y) / np.sum(w)
        return float(np.sum(w * (y - m) ** 2))

    tentativi = []
    try:
        p, cov = fit_once(p0, s_eff)
        tentativi.append((costo(p, s_eff), p, cov, False))
    except (RuntimeError, ValueError):
        pass
    da_stimare = len(set(range(len(p0))) - set(fixed)) > 0
    if not tentativi or (da_stimare and cattivo(tentativi[0][0], s_eff)):
        w = 1 / s_eff if weighted else np.ones_like(y)
        for start in _partenze(fs, x, y, w, p0, (lo, hi), set(fixed)):
            try:
                p, cov = fit_once(start, s_eff)
                tentativi.append((costo(p, s_eff), p, cov, True))
            except (RuntimeError, ValueError):
                continue
    if not tentativi:
        raise RuntimeError("il fit non converge: prova altri valori iniziali o dei limiti "
                           "ai parametri")
    _, p, cov, multi = min(tentativi, key=lambda t: t[0])
    if multi:
        note.append("risultato trovato con la ricerca multi-partenza dei valori iniziali "
                    "(quelli dati non portavano a un buon fit)")

    if sx is not None:
        base = sy if sy is not None else 0.0
        for _ in range(max_iter):
            with np.errstate(all="ignore"):
                deriv = np.asarray(dfdx(x, *p), float) * np.ones_like(x)
            deriv = np.where(np.isfinite(deriv), deriv, 0.0)
            s_new = np.sqrt(base ** 2 + (deriv * sx) ** 2)
            pos = s_new > 0
            if not pos.any():
                raise ValueError("con le sole σ x la derivata della legge è nulla in tutti i "
                                 "punti: aggiungi σ y")
            s_new = np.where(pos, s_new, s_new[pos].min())
            try:
                p_new, cov_new = fit_once(p, s_new)
            except (RuntimeError, ValueError):
                note.append("iterazione della varianza efficace interrotta: il fit non converge")
                break
            with np.errstate(invalid="ignore"):
                err = np.sqrt(np.abs(np.diag(cov_new)))
            fatto = np.all(np.abs(p_new - p) <= 1e-8 * np.abs(p) + 1e-4 * np.nan_to_num(err))
            s_eff, p, cov = s_new, p_new, cov_new
            if fatto:
                break
        else:
            note.append(f"varianza efficace non stabilizzata in {max_iter} iterazioni")

    yfit = fs(x, *p)
    res = y - yfit
    with np.errstate(invalid="ignore"):
        perr = np.sqrt(np.diag(cov))
    cov_ok = bool(np.all(np.isfinite(cov)))
    if not cov_ok:
        note.append("la covarianza non è stimabile (incertezze infinite): probabilmente due "
                    "parametri hanno lo stesso effetto sulla curva o i dati non bastano a "
                    "determinarli. Fissane qualcuno o semplifica la legge")
    elif len(p) > 1:
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = cov / np.outer(perr, perr)
        for i in range(len(p)):
            for j in range(i + 1, len(p)):
                if abs(corr[i, j]) > 0.999:
                    note.append(f"{names[i]} e {names[j]} sono correlati al "
                                f"{abs(corr[i, j]) * 100:.2f}%: i dati non li distinguono, "
                                "le loro incertezze singole non sono significative "
                                "(fissane uno o riscrivi la legge)")
    out = {"p": p, "cov": cov, "perr": perr, "ndof": ndof, "res": res, "yfit": yfit,
           "weighted": weighted, "s_eff": s_eff, "relativo": bool(relativo and weighted),
           "note": note, "cov_ok": cov_ok}
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
    args = [syms[n] for n in names]
    mod = ["scipy", "numpy"]
    for part in filter(None, [d.strip() for d in (defs or "").split(";")]):
        label, text = part.split("=", 1) if "=" in part else (part, part)
        label = label.strip()
        expr = _sympifica(text)
        extra = {s.name for s in expr.free_symbols} - set(names)
        if extra:
            raise ValueError(f"grandezza '{label}': simboli sconosciuti {', '.join(sorted(extra))}")
        val = float(sp.lambdify(args, expr, modules=mod, dummify=True)(*R["p"]))
        g = np.array([float(sp.lambdify(args, sp.diff(expr, a), modules=mod, dummify=True)(*R["p"]))
                      for a in args])
        with np.errstate(invalid="ignore"):
            out.append((label, val, float(np.sqrt(g @ R["cov"] @ g))))
    return out


def fmt_val(v, e):
    """Valore ± incertezza con 2 cifre significative sull'errore e lo stesso
    numero di decimali sul valore; notazione scientifica con esponente comune
    quando i numeri sono molto grandi o molto piccoli."""
    if not np.isfinite(v):
        return f"{v}"
    if not np.isfinite(e):
        return f"{v:.6g} ± {e}"
    if e <= 0:
        return f"{v:.6g}"
    ee = int(np.floor(np.log10(e)))
    ev = int(np.floor(np.log10(abs(v)))) if v != 0 else ee
    k = max(ev, ee)
    d = 1 - ee
    if -3 <= k <= 5 and d <= 6:
        d = max(0, d)
        return f"{v:.{d}f} ± {e:.{d}f}"
    dm = max(0, k - ee + 1)
    return f"({v / 10**k:.{dm}f} ± {e / 10**k:.{dm}f})e{k:+03d}"


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
        if R["relativo"]:
            L.append("σ usate come pesi relativi: incertezze dei parametri scalate di "
                     f"√(chi2 ridotto) = {np.sqrt(R['chi2r']):.3g};")
            L.append("chi2 e p-value non sono quindi un test della bontà del fit.")
        else:
            if R["ndof"] > 0:
                lo, hi = stats.chi2.ppf([0.025, 0.975], R["ndof"]) / R["ndof"]
                L.append(f"(intervallo atteso al 95% per il chi2 ridotto: {lo:.2f} – {hi:.2f})")
            L.append("Incertezze dei parametri dalle sigma dei dati (absolute_sigma).")
    else:
        L.append(f"Nessuna sigma sui dati: deviazione standard dei residui = {R['s_res']:.4g}")
        L.append("Incertezze dei parametri stimate dalla dispersione dei residui;")
        L.append("chi2 e p-value non sono calcolabili senza incertezze sui dati.")
    if R["ndof"] <= 0:
        L.append("Attenzione: tanti punti quanti parametri, nessun grado di libertà.")
    L.append(f"R^2 = {R['R2']:.6f}")
    if len(names) > 1:
        d = np.sqrt(np.abs(np.diag(R["cov"])))
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = R["cov"] / np.outer(d, d)
        L.append("\nMatrice di correlazione:")
        L.append("           " + "".join(f"{nm:>9s}" for nm in names))
        for nm, row in zip(names, corr):
            L.append(f"  {nm:>8s} " + "".join(f"{c:9.3f}" for c in row))
    if R.get("note"):
        L.append("\nNote:")
        L.extend(f"  - {t}" for t in R["note"])
    return "\n".join(L)


def testo_derivate(D):
    return "\n\nGrandezze derivate (propagazione con covarianza completa):\n" + "\n".join(
        f"  {lb:>10s} = {fmt_val(v, e)}"
        + (f"  ({abs(e / v) * 100:.2g} %)" if v and np.isfinite(e) else "")
        for lb, v, e in D)


def fit_tabella(legge, tabella, x, y, sy, sx, derivate="", sorgente="dati", relativo=False):
    """Fit completo, usato sia dall'interfaccia grafica sia dalla riga di
    comando (cosi' lo stesso report da' lo stesso fit in entrambe).

    tabella: {nome: (valore_iniziale|None, minimo|None, massimo|None, fisso)}
    I parametri fissati vengono tenuti al loro valore e tolti dal fit.
    Restituisce un dizionario con risultati e testo del report.
    """
    expr, names, f, dfdx = parse_law(legge)
    ignoti = set(tabella) - set(names)
    if ignoti:
        raise ValueError(f"parametri non presenti nella legge: {', '.join(sorted(ignoti))}")
    riga = lambda n: tabella.get(n, (None, None, None, False))
    fissi = {n: riga(n)[0] for n in names if riga(n)[3]}
    for n, v in fissi.items():
        if v is None:
            raise ValueError(f"il parametro {n} è fissato ma non ha un valore")
    liberi = [n for n in names if n not in fissi]
    if not liberi:
        raise ValueError("tutti i parametri sono fissati: lasciane libero almeno uno")
    if len(x) < len(liberi):
        raise ValueError(f"{len(x)} punti per {len(liberi)} parametri liberi: "
                         "allarga l'intervallo o fissa qualche parametro")
    controlla_sigma(sy, sx, x)

    idx = [names.index(n) for n in liberi]
    base = np.array([fissi.get(n, 0.0) for n in names], float)

    def allarga(g):
        def h(xx, *q):
            pieno = base.copy()
            pieno[idx] = q
            return g(xx, *pieno)
        return h

    utente = {n: riga(n)[0] for n in liberi if riga(n)[0] is not None}
    p0 = guess_p0(liberi, x, y, utente)
    lo = [-np.inf if riga(n)[1] is None else riga(n)[1] for n in liberi]
    hi = [np.inf if riga(n)[2] is None else riga(n)[2] for n in liberi]
    for n, a, b in zip(liberi, lo, hi):
        if a >= b:
            raise ValueError(f"limiti di {n}: il minimo deve essere minore del massimo")
    dati_utente = [i for i, n in enumerate(liberi) if n in utente]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        R = do_fit(allarga(f), allarga(dfdx), liberi, x, y, sy, sx, p0, (lo, hi),
                   dati_utente, relativo=relativo)

    p_pieno = base.copy()
    p_pieno[idx] = R["p"]
    perr_pieno = np.zeros(len(names))
    perr_pieno[idx] = R["perr"]
    cov_piena = np.zeros((len(names), len(names)))
    cov_piena[np.ix_(idx, idx)] = R["cov"]

    testo = report(expr, liberi, R, "x", sorgente, len(x))
    if fissi:
        testo += "\n\nParametri fissati (non entrano nel fit):\n" + "\n".join(
            f"  {n:>10s} = {v:.6g}" for n, v in fissi.items())
    D = []
    if (derivate or "").strip():
        try:
            D = derived(derivate, names, {"p": p_pieno, "cov": cov_piena})
        except Exception as e:
            raise ValueError(f"grandezza derivata non valida: {e}")
        testo += testo_derivate(D)

    return {"expr": expr, "names": names, "liberi": liberi, "fissi": fissi, "R": R,
            "p": p_pieno, "perr": perr_pieno, "derivate": D, "testo": testo,
            "curva": lambda xs: valuta_curva(f, xs, p_pieno)}


def maschera_intervallo(x, lo, hi):
    """Punti con lo <= x <= hi (estremi None = nessun limite)."""
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    m = np.ones(len(x), bool)
    if lo is not None:
        m &= x >= lo
    if hi is not None:
        m &= x <= hi
    return m


# --------------------------------------------------------------------------
# Impostazioni salvate nel report, per riaprire esattamente lo stesso fit
# --------------------------------------------------------------------------
INIZIO_IMPOSTAZIONI = ("=== Impostazioni del fit (servono per riaprirlo con "
                       "\"Riapri da report\" o --da-report: non modificarle) ===")
FINE_IMPOSTAZIONI = "=== Fine impostazioni ==="


def _jn(v):
    """Numero per il JSON: None per valori assenti o non finiti."""
    if v is None:
        return None
    v = float(v)
    return v if np.isfinite(v) else None


def impronta_file(path):
    """SHA-256 del file, per accorgersi se i dati sono cambiati."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def versioni():
    import scipy
    return {"python": sys.version.split()[0], "numpy": str(np.__version__),
            "scipy": str(scipy.__version__), "sympy": str(getattr(sp, "__version__", "?"))}


def descrivi_sigma(spec, arr=None):
    """Descrizione di una scelta di sigma della riga di comando."""
    if spec is None or str(spec).strip().lower() in ("", "nessuna", "none", "no"):
        return {"tipo": "nessuna"}
    s = str(spec).strip()
    if arr is not None and re.fullmatch(r"\d+", s):
        return {"tipo": "colonna", "colonna": int(s)}
    return {"tipo": "formula", "formula": formula_errore(s), "nome": s if s in ERRORI else None}


def crea_impostazioni(sorgente, legge, tabella, derivate, relativo, ris, n_punti,
                      nome_legge=None):
    """Tutto quello che serve per rifare il fit. sorgente: dizionario con tipo
    ('spe', 'tabella' o 'manuale'), file, percorso, x, y (colonne, None = n° di
    riga), energia, sigma_y, sigma_x, intervallo, dati (solo se manuali)."""
    imp = {"versione": 1}
    imp.update(sorgente)
    if imp.get("percorso") and os.path.exists(imp["percorso"]):
        imp["impronta"] = impronta_file(imp["percorso"])
    imp.update({
        "relativo": bool(relativo), "legge": legge, "nome_legge": nome_legge,
        "parametri": {n: {"iniziale": _jn(v), "min": _jn(a), "max": _jn(b), "fisso": bool(fx)}
                      for n, (v, a, b, fx) in tabella.items()},
        "derivate": derivate or "", "n_punti": int(n_punti),
        "risultati": {n: [_jn(v), _jn(e)] for n, v, e in zip(ris["names"], ris["p"], ris["perr"])},
        "chi2": _jn(ris["R"].get("chi2")), "versioni": versioni()})
    return imp


def blocco_impostazioni(imp):
    # JSON con una voce per riga: leggibile e ancora JSON valido
    corpo = ",\n".join(f" {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}"
                       for k, v in imp.items())
    return "\n\n" + INIZIO_IMPOSTAZIONI + "\n{\n" + corpo + "\n}\n" + FINE_IMPOSTAZIONI + "\n"


def _valore_report(s):
    """Primo valore di una riga di parametro: '3.14 ± 0.01' o '(1.2 ± 0.1)e+05'."""
    s = s.strip()
    m = re.match(r"\(\s*([-+]?[0-9.]+)\s*±[^)]*\)e([-+]?\d+)", s)
    if m:
        return float(m.group(1)) * 10.0 ** int(m.group(2))
    m = re.match(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", s)
    if m:
        return float(m.group(0))
    raise ValueError(s)


def _impostazioni_da_testo(testo):
    """Report senza blocco delle impostazioni (versioni precedenti): si
    ricostruiscono file, intervallo, legge e parametri (risultati come valori
    iniziali). Mancano sigma, limiti, colonne e definizioni delle derivate."""
    imp = {"versione": 0, "parametri": {}, "risultati": {}}
    sezione = None
    for r in testo.splitlines():
        m = re.match(r"Dati: (.*?)(?: \[([^\],]+), ([^\]]+)\])?  \((\d+) punti\)\s*$", r)
        if m:
            imp["file"], imp["n_punti"] = m.group(1), int(m.group(4))
            if m.group(2):
                lo, hi = float(m.group(2)), float(m.group(3))
                eps = 1e-5 * max(abs(lo), abs(hi), 1e-300)   # estremi scritti con 6 cifre
                imp["intervallo"] = [lo - eps, hi + eps]
            continue
        if r.startswith("Legge: y = "):
            imp["legge"] = r[len("Legge: y = "):].strip()
            continue
        if r.startswith("Parametri fissati"):
            sezione = "fissi"
            continue
        if r.startswith("Parametri:"):
            sezione = "par"
            continue
        if not r.strip():
            sezione = None
            continue
        m = re.match(r"^\s+([A-Za-z_]\w*) = (.+)$", r)
        if m and sezione:
            try:
                v = _valore_report(m.group(2))
            except ValueError:
                continue
            imp["parametri"][m.group(1)] = {"iniziale": v, "min": None, "max": None,
                                            "fisso": sezione == "fissi"}
            if sezione == "par":
                imp["risultati"][m.group(1)] = [v, None]
    if "legge" not in imp:
        raise ValueError("non sembra un report di questo programma: manca la riga 'Legge: y = ...'")
    imp["completo"] = False
    return imp


def leggi_impostazioni(testo):
    """Impostazioni da un report. Con un report delle versioni precedenti
    ricostruisce quello che si puo' e mette completo=False."""
    i = testo.find(INIZIO_IMPOSTAZIONI)
    if i < 0:
        return _impostazioni_da_testo(testo)
    j = testo.find(FINE_IMPOSTAZIONI, i)
    if j < 0:
        raise ValueError("il blocco delle impostazioni è incompleto")
    try:
        imp = json.loads(testo[i + len(INIZIO_IMPOSTAZIONI):j])
    except ValueError as e:
        raise ValueError(f"impostazioni non leggibili ({e}): il report è stato modificato?")
    if not isinstance(imp, dict) or not isinstance(imp.get("legge"), str):
        raise ValueError("impostazioni del report non valide")
    imp["completo"] = True
    return imp


def trova_file_dati(imp, path_report):
    """Percorso del file dei dati: quello registrato, oppure un file con lo
    stesso nome nella cartella del report o in quella corrente."""
    nome = imp.get("file")
    candidati = [imp.get("percorso")]
    if nome:
        candidati += [os.path.join(os.path.dirname(os.path.abspath(path_report)), nome),
                      os.path.abspath(nome)]
    for c in candidati:
        if c and os.path.isfile(c):
            return c
    return None


def tabella_da_impostazioni(imp):
    return {n: (p.get("iniziale"), p.get("min"), p.get("max"), bool(p.get("fisso")))
            for n, p in (imp.get("parametri") or {}).items()}


def confronta_risultati(imp, ris, n_punti, path_dati=None):
    """Confronta il fit rifatto con quello registrato nel report.
    Restituisce (esito, righe): esito e' 'identico', 'equivalente' o 'diverso'."""
    vecchi = imp.get("risultati") or {}
    righe, diversi, max_sig, identico = [], [], 0.0, True
    if imp.get("n_punti") is not None and imp["n_punti"] != n_punti:
        identico = False
        diversi.append(f"punti nel fit: {n_punti} invece di {imp['n_punti']}")
    for n, v, e in zip(ris["names"], ris["p"], ris["perr"]):
        if n not in vecchi or vecchi[n][0] is None:
            continue
        v0, e0 = vecchi[n]
        if v != v0:
            identico = False
        scala = e0 if e0 else (e if np.isfinite(e) and e > 0 else abs(v0) or 1.0)
        rapporto = abs(v - v0) / scala
        max_sig = max(max_sig, rapporto)
        soglia = 0.01 if imp.get("completo") else 0.06    # i report vecchi hanno valori arrotondati
        if rapporto > soglia:
            diversi.append(f"{n} = {fmt_val(v, e)} invece di {v0:.8g}")
    if path_dati and imp.get("impronta") and impronta_file(path_dati) != imp["impronta"]:
        righe.append("Il file dei dati non è identico a quello del fit originale.")
    if imp.get("versioni") and imp["versioni"] != versioni() and not identico:
        righe.append("Versioni di python/numpy/scipy/sympy diverse da quelle del fit "
                     "originale: possono cambiare le ultime cifre.")
    if diversi:
        return "diverso", ["Risultati diversi da quelli del report:"] + diversi + righe
    if identico and imp.get("completo"):
        return "identico", ["Fit riprodotto: parametri identici a quelli del report."] + righe
    return "equivalente", [f"Fit riprodotto: parametri uguali a quelli del report entro "
                           f"{max_sig:.2g} volte l'incertezza."] + righe


def plot(x, y, sy, sx, curva, R, righe_box, titolo, xlabel, ylabel, logy, path, logx=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1]})
    a1.errorbar(x, y, yerr=sy, xerr=sx, fmt="o", ms=3, lw=0.8, capsize=1.5, label="dati")
    logx = logx and bool(np.any(x > 0))
    if logx:
        xp = x[x > 0]
        xs = np.geomspace(xp.min(), xp.max(), 800)
    else:
        xs = np.linspace(x.min(), x.max(), 800)
    a1.plot(xs, curva(xs), "r-", lw=1.5, label="fit")
    txt = "\n".join(righe_box)
    if R["weighted"]:
        txt += f"\nχ²/ndf = {R['chi2']:.1f}/{R['ndof']}"
    a1.text(0.02, 0.97, txt, transform=a1.transAxes, va="top", fontsize=9,
            family="monospace", bbox=dict(fc="white", alpha=0.8, lw=0.5))
    import textwrap
    a1.set_title("\n".join(textwrap.wrap(titolo, 95)), fontsize=9)
    a1.set_ylabel(ylabel); a1.legend(loc="upper right")
    if logy and np.any(y > 0):
        a1.set_yscale("log")
    if logx:
        a1.set_xscale("log")
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


def _filtra(x, y, sy, sx):
    m = punti_validi(x, y, sy, sx)
    if (~m).any():
        print(f"  esclusi {int((~m).sum())} punti con valori mancanti o non finiti")
    sel = lambda a: None if a is None else a[m]
    return x[m], y[m], sel(sy), sel(sx)


def dati_manuali(rows):
    """Righe x y [sigma_y [sigma_x]] -> x, y, sy, sx."""
    n = min(len(r) for r in rows)
    arr = np.array([[np.nan if v is None else v for v in r[:n]] for r in rows], float)
    sy = arr[:, 2] if n > 2 else None
    sx = arr[:, 3] if n > 3 else None
    return arr, _filtra(arr[:, 0], arr[:, 1], sy, sx)


def load_data(a, interactive):
    """Restituisce x, y, sy, sx, etichette, descrizione della sorgente e un
    dizionario con le scelte fatte (per le impostazioni del report)."""
    path = a.file
    if interactive and not path:
        path = ask("File di dati (.csv/.txt/.Spe), oppure invio per inserirli a mano")
    rng = list(a.range) if a.range and any(v is not None for v in a.range) else None
    if not path:
        print("Inserisci una riga per punto: x y [sigma_y [sigma_x]]. Riga vuota per finire.")
        rows = []
        while True:
            s = input("> ").strip()
            if not s:
                break
            sep, virg = _separatore([s])             # stesse regole dei file
            toks = s.split() if sep is None else s.split(sep)
            try:
                rows.append([_numero(t, virg) for t in toks if t.strip()])
            except ValueError:
                print("  riga ignorata: servono numeri")
        if len(rows) < 2:
            raise ValueError("servono almeno due punti")
        arr, (x, y, sy, sx) = dati_manuali(rows)
        info = {"tipo": "manuale", "file": None, "dati": [[_jn(v) for v in r] for r in arr]}
        return x, y, sy, sx, "x", "y", "dati inseriti a mano", info

    info = {"file": os.path.basename(path), "percorso": os.path.abspath(path)}
    if path.lower().endswith(".spe"):
        d = read_spe_full(path)
        counts, cal = d["counts"], d["cal"]
        ch = d["primo"] + np.arange(len(counts), dtype=float)
        use_e = cal is not None and not a.channels
        xv = sum(c * ch**k for k, c in enumerate(cal)) if use_e else ch
        var = {"x": xv, "y": counts, "ch": ch}
        spec_y = a.sy if a.sy is not None else "poisson"
        sy = risolvi_sigma(spec_y, var, len(ch))
        sx = risolvi_sigma(a.sx, var, len(ch))
        if interactive and rng is None:
            r = ask(f"Intervallo in {d['unita'] if use_e else 'canali'} (min max), "
                    "invio per tutto", "")
            rng = [float(v) for v in r.replace(",", ".").split()] if r else None
        lo, hi = rng if rng else (None, None)
        m = maschera_intervallo(xv, lo, hi)
        sel = lambda v: None if v is None else v[m]
        x, y, sy, sx = _filtra(xv[m], counts[m], sel(sy), sel(sx))
        info.update(tipo="spe", energia=bool(use_e), intervallo=[_jn(lo), _jn(hi)],
                    sigma_y=descrivi_sigma(spec_y), sigma_x=descrivi_sigma(a.sx))
        return (x, y, sy, sx, f"Energia [{d['unita']}]" if use_e else "Canale", "Conteggi",
                f"{os.path.basename(path)}" + (f" [{x.min():g}, {x.max():g}]" if rng and len(x) else ""),
                info)

    t = read_table(path)
    arr, nomi = t["arr"], t["nomi"]
    print(f"Lette {arr.shape[0]} righe e {arr.shape[1]} colonne da {path} "
          f"(separatore: {SEPARATORI[t['sep']]}" + (", virgola decimale" if t["virgola"] else "")
          + ")" + (f"; scartate {t['scartate']} righe con un numero di colonne diverso"
                   if t["scartate"] else ""))
    if nomi:
        print("Colonne: " + ", ".join(f"{i}={nm}" for i, nm in enumerate(nomi)))
    if interactive and a.y is None:
        print("Prime righe:\n" + "\n".join("  " + "  ".join(f"{v:g}" for v in r) for r in arr[:3]))
        a.x = int(ask("Colonna di x (da 0; -1 = numero di riga)", 0))
        a.y = int(ask("Colonna di y", 1))
        s = ask("σ y: numero di colonna, 'poisson', formula (es. 0.05*y) o nome del menu "
                f"({', '.join(ERRORI)}); invio se assente", "")
        a.sy = None if s == "" else s
        s = ask("σ x: come sopra; invio se assente", "")
        a.sx = None if s == "" else s
    x, y, sy, sx, scelte = estrai_tabella(arr, nomi, a.x, a.y, a.sy, a.sx, rng)
    info.update(tipo="tabella", **scelte)
    src = os.path.basename(path) + (f" [{x.min():g}, {x.max():g}]" if rng and len(x) else "")
    return x, y, sy, sx, a.xlabel or "x", a.ylabel or "y", src, info


def estrai_tabella(arr, nomi, xi, yi, sy_spec, sx_spec, rng):
    """x, y, sigma da una tabella secondo le scelte (colonne, sigma come
    colonna/formula, intervallo); restituisce anche le scelte per il report."""
    xi = xi if xi is not None else (0 if arr.shape[1] > 1 else -1)
    yi = yi if yi is not None else (1 if arr.shape[1] > 1 else 0)
    for i in (xi, yi):
        if i >= arr.shape[1]:
            raise ValueError(f"colonna {i} inesistente (la tabella ha {arr.shape[1]} colonne, da 0)")
    if xi < 0:
        print("x = numero di riga (0, 1, 2, ...)")
        x = np.arange(len(arr), dtype=float)
    else:
        x = arr[:, xi]
    y = arr[:, yi]
    var = variabili_tabella(arr, nomi, x, y)
    sy = risolvi_sigma(sy_spec, var, len(x), arr)
    sx = risolvi_sigma(sx_spec, var, len(x), arr)
    lo, hi = list(rng)[:2] if rng else (None, None)
    m = maschera_intervallo(x, lo, hi)
    sel = lambda v: None if v is None else v[m]
    x, y, sy, sx = _filtra(x[m], y[m], sel(sy), sel(sx))
    scelte = {"x": None if xi < 0 else int(xi), "y": int(yi), "intervallo": [_jn(lo), _jn(hi)],
              "sigma_y": descrivi_sigma(sy_spec, arr), "sigma_x": descrivi_sigma(sx_spec, arr)}
    return x, y, sy, sx, scelte


# --------------------------------------------------------------------------
# Punti scritti a mano: (x, y) (σx, σy), con le sigma facoltative
# --------------------------------------------------------------------------
def _elenco(numeri, n=8):
    s = ", ".join(map(str, numeri[:n]))
    return s + (", …" if len(numeri) > n else "")


def _valori_gruppo(g, virgola):
    """Valori di un gruppo tra parentesi; None per un posto lasciato vuoto."""
    if ";" in g:
        parti, dec = g.split(";"), True
    elif "," in g and not virgola:
        parti, dec = g.split(","), False
    elif "," in g:                        # virgola decimale, un solo valore: (0,1)
        parti, dec = [g], True
    else:
        parti, dec = (g.split() or [""]), False
    out = []
    for t in parti:
        t = t.strip()
        if t in ("", "-"):
            out.append(None)
            continue
        try:
            out.append(float(t.replace(",", ".") if dec else t))
        except ValueError:
            raise ValueError(f"'{t}' non è un numero")
    return out


def _punto(s, virgola, singolo):
    gruppi = re.findall(r"\(([^()]*)\)", s)
    if gruppi:
        if re.sub(r"\([^()]*\)", " ", s).strip(" ,;\t"):
            raise ValueError("c'è del testo fuori dalle parentesi")
        if len(gruppi) > 2:
            raise ValueError("al massimo due gruppi: (x, y) (σx, σy)")
        xy = _valori_gruppo(gruppi[0], virgola)
        if len(xy) != 2 or None in xy:
            consiglio = (" (con la virgola decimale separa i valori con ;  es. (1,5; 2,3))"
                         if len(xy) > 2 else "")
            raise ValueError("il primo gruppo deve contenere x e y" + consiglio)
        sigma = _valori_gruppo(gruppi[1], virgola) if len(gruppi) == 2 else [None, None]
    else:                                 # senza parentesi: x y [σx σy]
        sep, dec = _separatore([s])
        toks = s.split() if sep is None else s.split(sep)
        vals = []
        for t in toks:
            t = t.strip()
            if t in ("", "-"):
                vals.append(None)
                continue
            try:
                vals.append(_numero(t, dec))
            except ValueError:
                raise ValueError(f"'{t}' non è un numero")
        if len(vals) not in (2, 3, 4) or None in vals[:2]:
            raise ValueError("servono x e y, eventualmente seguiti da σx σy")
        xy, sigma = vals[:2], (vals[2:] or [None, None])
    if len(sigma) == 1:
        sigma = [None, sigma[0]] if singolo == "sy" else [sigma[0], None]
    if len(sigma) != 2:
        raise ValueError("il secondo gruppo deve essere (σx, σy)")
    return xy[0], xy[1], sigma[0], sigma[1]


def leggi_punti(testo, singolo="sy"):
    """Punti scritti uno per riga come (x, y) oppure (x, y) (σx, σy). Un posto
    vuoto omette quella sigma: (x, y) (, σy) oppure (x, y) (σx, ). Un solo
    valore nel secondo gruppo vale come σy (singolo="sy") o σx ("sx").
    Senza parentesi: x y [σx σy]. Con la virgola decimale si separano i valori
    con ';': (1,5; 2,3) (0,1; 0,2). Righe vuote e commenti (#) ignorati.
    Restituisce (array con colonne x, y e le sigma presenti, nomi delle sigma)."""
    virgola = bool(re.search(r"\([^()]*;[^()]*\)", testo))
    righe = []
    for nr, riga in enumerate(testo.splitlines(), 1):
        s = riga.split("#", 1)[0].strip()
        if not s:
            continue
        try:
            righe.append((nr,) + _punto(s, virgola, singolo))
        except ValueError as e:
            raise ValueError(f"riga {nr} «{riga.strip()}»: {e}")
    if len(righe) < 2:
        raise ValueError("servono almeno due punti")
    colonne, nomi = [[r[1] for r in righe], [r[2] for r in righe]], []
    for i, nome, chiave in ((3, "σx", "sx"), (4, "σy", "sy")):
        con = [r[0] for r in righe if r[i] is not None]
        if not con:
            continue
        if len(con) < len(righe):
            senza = [r[0] for r in righe if r[i] is None]
            raise ValueError(f"{nome} è data solo per alcuni punti: manca alle righe "
                             f"{_elenco(senza)}. Dalla a tutti i punti o a nessuno")
        cattive = [r[0] for r in righe if (r[i] < 0 if chiave == "sx" else r[i] <= 0)]
        if cattive:
            raise ValueError(f"{nome} {'negativa' if chiave == 'sx' else 'nulla o negativa'} "
                             f"alle righe {_elenco(cattive)}")
        colonne.append([r[i] for r in righe])
        nomi.append(chiave)
    return np.array(colonne, float).T, nomi


def testo_punti(arr, nomi):
    """Testo nel formato di leggi_punti, per modificare dei dati gia' inseriti."""
    isx = nomi.index("sx") if "sx" in nomi[2:] else None
    isy = nomi.index("sy") if "sy" in nomi[2:] else None
    v = lambda t: repr(float(t))
    righe = []
    for r in arr:
        s = f"({v(r[0])}, {v(r[1])})"
        if isx is not None or isy is not None:
            s += (f" ({v(r[isx]) if isx is not None else ''}, "
                  f"{v(r[isy]) if isy is not None else ''})")
        righe.append(s)
    return "\n".join(righe)


def tabella_da_testo(names, p0_text, bounds_text, fissi_text=""):
    """Valori iniziali, limiti e parametri fissati scritti come testo."""
    user, fissi = parse_kv(p0_text), parse_kv(fissi_text)
    unknown = (set(user) | set(fissi)) - set(names)
    if unknown:
        raise ValueError(f"parametri non presenti nella legge: {', '.join(sorted(unknown))}")
    lo, hi = parse_bounds(bounds_text, names)
    fin = lambda v: v if np.isfinite(v) else None
    return {n: (fissi.get(n, user.get(n)), fin(a), fin(b), n in fissi)
            for n, a, b in zip(names, lo, hi)}


def run_fit(law, tabella, x, y, sy, sx, labels, src, outdir, tag, logy,
            der_text="", relativo=False, logx=False, info=None):
    """Fit da riga di comando: stampa e salva report (con le impostazioni per
    riaprirlo), tabella dei punti e grafico."""
    nome_legge = None
    if law.strip() in LEGGI:
        nome_legge = law.strip()
        law = LEGGI[nome_legge][0]
    ris = fit_tabella(law, tabella, x, y, sy, sx, der_text, src, relativo)
    R = ris["R"]
    txt = ris["testo"]
    print("\n" + txt + "\n")
    os.makedirs(outdir, exist_ok=True)
    base = os.path.join(outdir, tag)
    with open(base + "_report.txt", "w", encoding="utf-8") as fh:
        fh.write(txt + "\n")
        if info is not None:
            fh.write(blocco_impostazioni(crea_impostazioni(info, law, tabella, der_text, relativo,
                                                           ris, len(x), nome_legge)))
    cols, hdr = [x, y], ["x", "y"]
    for a, nm in ((sy, "sigma_y"), (sx, "sigma_x")):
        if a is not None:
            cols.append(a); hdr.append(nm)
    if sx is not None:
        cols.append(R["s_eff"]); hdr.append("sigma_efficace")
    cols += [R["yfit"], R["res"]]; hdr += ["y_fit", "residuo"]
    np.savetxt(base + "_fit.csv", np.column_stack(cols), delimiter=",", header=",".join(hdr),
               comments="", fmt="%.8g")
    box = [f"{n} = {fmt_val(v, e)}" for n, v, e in zip(ris["liberi"], R["p"], R["perr"])]
    box += [f"{n} = {v:.6g} (fisso)" for n, v in ris["fissi"].items()]
    plot(x, y, sy, sx, ris["curva"], R, box, f"y = {sp.sstr(ris['expr'])}",
         labels[0], labels[1], logy, base + "_fit.png", logx)
    print(f"Salvati: {base}_report.txt, {base}_fit.csv, {base}_fit.png")
    return ris


def _da_report(a):
    """Prepara a (argomenti) dal report indicato con --da-report.
    Restituisce (impostazioni, tabella, dati manuali o None)."""
    with open(a.da_report, encoding="utf-8", errors="replace") as f:
        imp = leggi_impostazioni(f.read())
    if not imp["completo"]:
        print("Report di una versione precedente: ripristino legge, intervallo e parametri "
              "(risultati come valori iniziali). σ, colonne, limiti e derivate non sono "
              "registrati: uso quelli indicati sulla riga di comando o i predefiniti.")
    manuali = None
    if imp.get("tipo") == "manuale":
        manuali = imp.get("dati")
        if not manuali:
            raise ValueError("il report non contiene i dati inseriti a mano")
    else:
        path = trova_file_dati(imp, a.da_report)
        if path is None:
            raise ValueError(f"non trovo il file dei dati '{imp.get('file')}': mettilo nella "
                             "cartella del report")
        a.file = path
    a.legge = imp["legge"]
    if imp.get("nome_legge") in LEGGI and LEGGI[imp["nome_legge"]][0] == imp["legge"]:
        a.legge = imp["nome_legge"]                  # per riportare il nome nel nuovo report
    if "intervallo" in imp:
        a.range = imp["intervallo"]
    if imp["completo"]:
        a.derivate = imp.get("derivate", "")
        a.relativo = bool(imp.get("relativo"))
        if imp.get("tipo") == "spe":
            a.channels = not imp.get("energia", True)
        elif imp.get("tipo") == "tabella" or (imp.get("tipo") == "manuale" and "y" in imp):
            a.x = -1 if imp.get("x") is None else imp["x"]
            a.y = imp["y"]
        for k, attr in (("sigma_y", "sy"), ("sigma_x", "sx")):
            s = imp.get(k) or {"tipo": "nessuna"}
            if s["tipo"] == "colonna":
                setattr(a, attr, str(s["colonna"]))
            elif s["tipo"] == "formula":
                f = s["formula"]
                # un intero da solo sarebbe letto come numero di colonna
                setattr(a, attr, f + ".0" if re.fullmatch(r"\d+", f.strip()) else f)
            else:
                setattr(a, attr, "nessuna")
    return imp, tabella_da_impostazioni(imp), manuali


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="file di dati (.csv/.txt/.dat/.Spe)")
    ap.add_argument("--x", type=int, help="colonna di x (da 0; -1 = numero di riga)")
    ap.add_argument("--y", type=int, help="colonna di y")
    ap.add_argument("--sy", help="σ y: colonna, 'poisson', nome del menu o formula (es. '0.05*y')")
    ap.add_argument("--sx", help="σ x: colonna, nome del menu o formula")
    ap.add_argument("--range", type=float, nargs=2, metavar=("MIN", "MAX"),
                    help="intervallo di x da fittare")
    ap.add_argument("--channels", action="store_true", help=".Spe: usa i canali anche se calibrato")
    ap.add_argument("--legge", help="espressione in x oppure nome di una legge del menu")
    ap.add_argument("--p0", default="", help="valori iniziali, es. 'a=1,b=0.5'")
    ap.add_argument("--bounds", default="", help="limiti, es. 's:0:,A:0:1e6'")
    ap.add_argument("--fissi", default="", help="parametri fissati, es. 'p1=0'")
    ap.add_argument("--derivate", default="",
                    help="grandezze dai parametri, separate da ';', es. 'area=A*s*sqrt(2*pi)'")
    ap.add_argument("--relativo", action="store_true",
                    help="σ come pesi relativi: incertezze scalate con √chi2 ridotto")
    ap.add_argument("--da-report", metavar="REPORT",
                    help="rifà il fit di un report salvato (stesso file, stesse impostazioni)")
    ap.add_argument("--xlabel"); ap.add_argument("--ylabel")
    ap.add_argument("--logy", action="store_true")
    ap.add_argument("--logx", action="store_true")
    ap.add_argument("--outdir", default="fit_out")
    ap.add_argument("--tag", default="fit", help="prefisso dei file di uscita")
    a = ap.parse_args()
    for avviso in carica_menu_utente():
        print(f"Attenzione: {avviso}; uso i valori predefiniti.", file=sys.stderr)

    imp = tabella = manuali = None
    if a.da_report:
        try:
            imp, tabella, manuali = _da_report(a)
        except (OSError, ValueError) as e:
            sys.exit(f"Report non utilizzabile: {e}")
    interactive = a.legge is None

    try:
        if manuali is not None and imp.get("nomi"):
            # dati inseriti nella GUI: tabella con i nomi delle colonne
            arr = np.array([[np.nan if v is None else v for v in r] for r in manuali], float)
            x, y, sy, sx, scelte = estrai_tabella(arr, imp["nomi"], a.x, a.y, a.sy, a.sx, a.range)
            xl = "n° di riga" if scelte["x"] is None else imp["nomi"][scelte["x"]]
            yl, src = imp["nomi"][scelte["y"]], "dati inseriti a mano"
            info = {"tipo": "manuale", "file": None, "dati": manuali, "nomi": imp["nomi"], **scelte}
        elif manuali is not None:
            _, (x, y, sy, sx) = dati_manuali(manuali)
            xl, yl, src = "x", "y", "dati inseriti a mano"
            info = {"tipo": "manuale", "file": None, "dati": manuali}
        else:
            x, y, sy, sx, xl, yl, src, info = load_data(a, interactive)
    except (OSError, ValueError) as e:
        sys.exit(f"Errore nei dati: {e}")
    if len(x) < 2:
        sys.exit("Errore nei dati: meno di due punti nell'intervallo scelto")
    print(f"{len(x)} punti, x in [{x.min():g}, {x.max():g}]"
          + ("" if sy is not None else "  (nessuna incertezza su y)"))

    if not interactive:
        try:
            if tabella is None:
                legge = LEGGI[a.legge.strip()][0] if a.legge.strip() in LEGGI else a.legge
                _, names, _, _ = parse_law(legge)
                tabella = tabella_da_testo(names, a.p0, a.bounds, a.fissi)
            ris = run_fit(a.legge, tabella, x, y, sy, sx, (xl, yl), src,
                          a.outdir, a.tag, a.logy, a.derivate, a.relativo, a.logx, info)
        except Exception as e:
            sys.exit(f"Fit non riuscito: {e}")
        if imp is not None:
            _, righe = confronta_risultati(imp, ris, len(x), a.file)
            print("\n".join(righe))
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
        fis = ask("  Parametri fissati (es. " + f"{names[-1]}=0" + "), invio per nessuno", "")
        der = ask("  Grandezze derivate (es. area=A*s*sqrt(2*pi)), invio per nessuna", "")
        k += 1
        try:
            run_fit(law, tabella_da_testo(names, p0, bnd, fis), x, y, sy, sx, (xl, yl), src,
                    a.outdir, f"{a.tag}{k}", a.logy, der, a.relativo, a.logx, info)
        except Exception as e:
            print(f"  Fit non riuscito: {e}\n  Prova a cambiare i valori iniziali o i limiti.")


if __name__ == "__main__":
    main()
