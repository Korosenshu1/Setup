#!/usr/bin/env python3
"""
fit_gui.py - Interfaccia grafica per il fit di dati con una legge scritta a mano.

Usa il motore di calcolo di fit_legge.py, che deve stare nella stessa cartella.

Avvio:   python fit_gui.py            (oppure: python fit_gui.py dati.csv)

Cosa si puo' fare:
  - aprire file a colonne (.csv .txt .dat) o spettri MAESTRO .Spe;
  - scegliere le colonne di x, y, sigma_y e sigma_x (o l'errore poissoniano);
  - scegliere l'intervallo del fit trascinando il mouse sul grafico;
  - scrivere la legge in funzione di x, o sceglierne una gia' pronta;
  - gestire il menu delle leggi pronte: aggiungerne con un nome a scelta,
    modificarle, rinominarle, rimuoverle o ripristinare quelle predefinite
    (salvate in leggi_utente.json accanto a questo file);
  - dare valori iniziali e limiti ai parametri, oppure fissarli;
  - vedere in anteprima la curva con i valori iniziali;
  - ottenere parametri, incertezze, chi quadro, correlazioni, residui e
    grandezze derivate con l'incertezza propagata;
  - salvare grafico (.png), report (.txt) e tabella dei punti (.csv).

Tasti: Ctrl+O apre un file, F5 esegue il fit.

Dipendenze: numpy, scipy, sympy, matplotlib, tkinter (incluso in Python su
Windows e macOS; su Linux Debian/Ubuntu: sudo apt install python3-tk).
"""
import contextlib
import io
import json
import os
import sys
import warnings

import numpy as np

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter import font as tkfont
except ImportError:
    sys.exit("Manca tkinter. Su Debian/Ubuntu: sudo apt install python3-tk. "
             "Su Windows e macOS e' incluso nell'installazione di python.org.")

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector

try:
    import fit_legge as eng
except ImportError as e:
    sys.exit(f"Non trovo fit_legge.py (o una sua dipendenza): {e}\n"
             "Metti fit_gui.py e fit_legge.py nella stessa cartella.")

NESSUNA = "nessuna"
POISSON = "poisson √y"
LIBERA = "(scrivi la tua)"

# Le leggi del menu stanno in un file JSON accanto al programma; se manca si
# usano quelle predefinite di fit_legge.py (copiate qui prima di ogni modifica).
FILE_LEGGI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leggi_utente.json")
PREDEFINITE = dict(eng.LEGGI)


# ==========================================================================
# Logica indipendente dall'interfaccia
# ==========================================================================
def carica_leggi(path=FILE_LEGGI):
    """Leggi del menu dal file JSON: {nome: {"legge": ..., "descrizione": ...}}.
    Restituisce (leggi, avviso); avviso e' None se tutto e' andato bene."""
    try:
        with open(path, encoding="utf-8") as f:
            dati = json.load(f)
    except FileNotFoundError:
        return dict(PREDEFINITE), None
    except (OSError, ValueError) as e:
        return dict(PREDEFINITE), f"{os.path.basename(path)} non leggibile ({e})"
    if not isinstance(dati, dict):
        return dict(PREDEFINITE), f"{os.path.basename(path)} non ha il formato atteso"
    leggi = {}
    for nome, voce in dati.items():
        if isinstance(voce, dict) and isinstance(voce.get("legge"), str):
            leggi[str(nome)] = (voce["legge"], str(voce.get("descrizione", "")))
    return leggi, None


def salva_leggi(leggi, path=FILE_LEGGI):
    """Scrive le leggi nel file JSON (prima su un file temporaneo, cosi' un
    errore a meta' scrittura non rovina il file esistente)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({n: {"legge": l, "descrizione": d} for n, (l, d) in leggi.items()},
                  f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def imposta_leggi(leggi):
    """Sostituisce le leggi del motore senza cambiare l'oggetto dizionario,
    cosi' anche eng.parse_law riconosce subito i nomi nuovi."""
    eng.LEGGI.clear()
    eng.LEGGI.update(leggi)


def controlla_legge(nome, legge):
    """Solleva ValueError se nome o espressione non vanno bene."""
    if not nome:
        raise ValueError("dai un nome alla legge")
    if nome == LIBERA:
        raise ValueError(f"il nome '{LIBERA}' è riservato")
    if not legge:
        raise ValueError("scrivi l'espressione della legge")
    if legge in eng.LEGGI:
        raise ValueError("scrivi l'espressione della legge, non il nome di una legge del menu")
    eng.parse_law(legge)                              # ValueError se non valida


def leggi_con(leggi, nome, legge, descr, vecchio=None):
    """Nuovo dizionario con la legge aggiunta o sostituita. Se vecchio e' dato
    (modifica, anche con cambio di nome) la voce resta al suo posto nel menu;
    un'altra legge con lo stesso nome nuovo viene sostituita."""
    voce = (legge, descr)
    posto = vecchio if vecchio in leggi else nome
    nuove = {}
    for k, v in leggi.items():
        if k == posto:
            nuove[nome] = voce
        elif k != nome:
            nuove[k] = v
    if nome not in nuove:
        nuove[nome] = voce
    return nuove


def num(testo, default=None):
    """Numero da una casella di testo; accetta la virgola decimale."""
    t = str(testo).strip().replace(",", ".")
    if not t:
        return default
    return float(t)


def intestazione(path, ncol):
    """Nomi delle colonne, se la riga prima dei dati ne contiene ncol."""
    import re
    try:
        with open(path, errors="ignore") as f:
            for line in f:
                s = line.strip().lstrip("#").strip()
                if not s:
                    continue
                toks = [t for t in re.split(r"[\s,;]+", s) if t]
                try:
                    [float(t) for t in toks]
                    return None                      # prima riga gia' numerica
                except ValueError:
                    if len(toks) == ncol:
                        return toks
    except OSError:
        pass
    return None


class Dati:
    """Un file caricato: tabella a colonne oppure spettro .Spe."""

    def __init__(self, path):
        self.path = path
        self.nome = os.path.basename(path)
        self.spe = path.lower().endswith(".spe")
        if self.spe:
            self.counts, self.cal, self.lt = eng.read_spe(path)
            self.etichette = []
        else:
            self.arr = eng.read_columns(path)
            if self.arr.shape[1] < 2:
                raise ValueError("servono almeno due colonne (x e y)")
            nomi = intestazione(path, self.arr.shape[1])
            self.etichette = [f"col {i}" + (f": {nomi[i]}" if nomi else "")
                              for i in range(self.arr.shape[1])]

    def estrai(self, x_et=None, y_et=None, sy_et=NESSUNA, sx_et=NESSUNA, kev=True):
        """Restituisce x, y, sigma_y, sigma_x, etichetta x, etichetta y."""
        if self.spe:
            ch = np.arange(len(self.counts), dtype=float)
            usa_e = bool(kev and self.cal)
            x = sum(c * ch**k for k, c in enumerate(self.cal)) if usa_e else ch
            y = self.counts
            sy = None if sy_et == NESSUNA else np.sqrt(np.clip(y, 1, None))
            return x, y, sy, None, "Energia [keV]" if usa_e else "Canale", "Conteggi"
        col = lambda et: self.arr[:, self.etichette.index(et)]
        x, y = col(x_et), col(y_et)
        if sy_et == NESSUNA:
            sy = None
        elif sy_et == POISSON:
            sy = np.sqrt(np.clip(y, 1, None))
        else:
            sy = col(sy_et)
        sx = None if sx_et == NESSUNA else col(sx_et)
        nome = lambda et: et.split(": ", 1)[1] if ": " in et else et
        return x, y, sy, sx, nome(x_et), nome(y_et)


def calcola_fit(legge, tabella, x, y, sy, sx, derivate="", sorgente="dati"):
    """Esegue il fit.

    tabella: {nome: (valore_iniziale|None, minimo|None, massimo|None, fisso)}
    I parametri fissati vengono tenuti al loro valore e tolti dal fit.
    Restituisce un dizionario con risultati e testo del report.
    """
    expr, names, f, dfdx = eng.parse_law(legge)
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
    if sy is not None and np.any(sy <= 0):
        raise ValueError("ci sono σ y nulle o negative")
    if sx is not None and np.any(sx < 0):
        raise ValueError("ci sono σ x negative")

    idx = [names.index(n) for n in liberi]
    base = np.array([fissi.get(n, 0.0) for n in names], float)

    def allarga(g):
        def h(xx, *q):
            pieno = base.copy()
            pieno[idx] = q
            return g(xx, *pieno)
        return h

    utente = {n: riga(n)[0] for n in liberi if riga(n)[0] is not None}
    p0 = eng.guess_p0(liberi, x, y, utente)
    lo = [-np.inf if riga(n)[1] is None else riga(n)[1] for n in liberi]
    hi = [np.inf if riga(n)[2] is None else riga(n)[2] for n in liberi]
    for n, a, b in zip(liberi, lo, hi):
        if a >= b:
            raise ValueError(f"limiti di {n}: il minimo deve essere minore del massimo")
    p0 = [min(max(v, a), b) for v, a, b in zip(p0, lo, hi)]
    dati_utente = [i for i, n in enumerate(liberi) if n in utente]

    uscita = io.StringIO()
    with contextlib.redirect_stdout(uscita), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        R = eng.do_fit(allarga(f), allarga(dfdx), liberi, x, y, sy, sx, p0, (lo, hi),
                       dati_utente)

    p_pieno = base.copy()
    p_pieno[idx] = R["p"]
    cov_piena = np.zeros((len(names), len(names)))
    cov_piena[np.ix_(idx, idx)] = R["cov"]

    testo = eng.report(expr, liberi, R, "x", sorgente, len(x))
    if fissi:
        testo += "\n\nParametri fissati (non entrano nel fit):\n" + "\n".join(
            f"  {n:>10s} = {v:.6g}" for n, v in fissi.items())
    nota = uscita.getvalue().strip()
    if nota:
        testo += "\n\nNota: " + nota.strip("() ")
    D = []
    if derivate.strip():
        try:
            D = eng.derived(derivate, names, {"p": p_pieno, "cov": cov_piena})
        except Exception as e:
            raise ValueError(f"grandezza derivata non valida: {e}")
        testo += "\n\nGrandezze derivate (propagazione con covarianza completa):\n" + "\n".join(
            f"  {et:>10s} = {eng.fmt_val(v, e)}" for et, v, e in D)

    curva = eng._safe(f)
    return {"expr": expr, "names": names, "liberi": liberi, "fissi": fissi, "R": R,
            "p": p_pieno, "derivate": D, "testo": testo,
            "curva": lambda xs: curva(np.asarray(xs, float), *p_pieno)}


# ==========================================================================
# Interfaccia
# ==========================================================================
class DialogoLegge(tk.Toplevel):
    """Finestra per scrivere nome, espressione e descrizione di una legge.
    Dopo la chiusura, self.risultato e' (nome, legge, descrizione) oppure None."""

    def __init__(self, parent, titolo, nome="", legge="", descr="", vecchio=None):
        super().__init__(parent)
        self.title(titolo)
        self.transient(parent)
        self.resizable(True, False)
        self.vecchio = vecchio
        self.risultato = None
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        self.v_nome, self.v_legge, self.v_descr = (tk.StringVar(value=nome),
                                                   tk.StringVar(value=legge),
                                                   tk.StringVar(value=descr))
        campi = (("Nome nel menu", self.v_nome, 24, "w"),
                 ("Legge  y =", self.v_legge, 64, "we"),
                 ("Descrizione", self.v_descr, 64, "we"))
        for r, (et, var, larg, sticky) in enumerate(campi):
            ttk.Label(f, text=et).grid(row=r, column=0, sticky="e", padx=(0, 6), pady=3)
            e = ttk.Entry(f, textvariable=var, width=larg)
            e.grid(row=r, column=1, sticky=sticky, pady=3)
            if r == 0:
                e.focus_set()
                e.select_range(0, "end")
        ttk.Label(f, text="La descrizione è facoltativa. Variabile: x; tutti gli altri "
                          "nomi sono parametri.", foreground="#555").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        b = ttk.Frame(f)
        b.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(b, text="Annulla", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Salva", command=self.ok).pack(side="right", padx=6)
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.destroy())
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.wait_window()

    def ok(self):
        nome, legge = self.v_nome.get().strip(), self.v_legge.get().strip()
        descr = self.v_descr.get().strip()
        try:
            controlla_legge(nome, legge)
        except ValueError as e:
            messagebox.showerror("Legge non valida", str(e), parent=self)
            return
        if nome != self.vecchio and nome in eng.LEGGI:
            if not messagebox.askyesno("Nome già usato",
                                       f"Nel menu c'è già una legge '{nome}'.\n"
                                       "Vuoi sostituirla?", parent=self):
                return
        self.risultato = (nome, legge, descr)
        self.destroy()


class App:
    def __init__(self, root, path=None):
        self.root = root
        root.title("Fit di dati con legge libera")
        root.geometry("1240x760")
        root.minsize(1000, 620)
        self.dati = None          # file caricato
        self.ris = None           # ultimo fit
        self.ante = None          # funzione di anteprima con i valori iniziali
        self.testo = ""           # testo del report mostrato
        self.righe = {}           # nome -> variabili della riga del parametro
        self.widget_par = []
        self.span = None
        leggi, avviso = carica_leggi()
        imposta_leggi(leggi)
        self._costruisci()
        root.bind("<Control-o>", lambda e: self.apri_dialogo())
        root.bind("<F5>", lambda e: self.esegui_fit())
        self.ridisegna()
        if avviso:
            self.stato(f"{avviso}: uso le leggi predefinite. Il file verrà riscritto "
                       "alla prossima modifica del menu.")
        if path:
            self.apri(path)

    # ------------------------------------------------------------ costruzione
    def _costruisci(self):
        root = self.root
        self.v_stato = tk.StringVar(value="Apri un file di dati per cominciare.")
        ttk.Label(root, textvariable=self.v_stato, anchor="w", relief="sunken",
                  padding=(6, 2)).pack(side="bottom", fill="x")
        pan = ttk.PanedWindow(root, orient="horizontal")
        pan.pack(fill="both", expand=True)
        sin = ttk.Frame(pan, padding=8)
        des = ttk.Frame(pan)
        pan.add(sin, weight=0)
        pan.add(des, weight=1)

        # ---- 1. dati
        f = ttk.LabelFrame(sin, text="1. Dati", padding=6)
        f.pack(fill="x")
        ttk.Button(f, text="Apri file…", command=self.apri_dialogo).grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.v_file = tk.StringVar(value="nessun file")
        ttk.Label(f, textvariable=self.v_file, width=30).grid(
            row=0, column=2, columnspan=2, sticky="w", padx=6)
        self.v_x, self.v_y = tk.StringVar(), tk.StringVar()
        self.v_sy, self.v_sx = tk.StringVar(value=NESSUNA), tk.StringVar(value=NESSUNA)
        self.cb = {}
        for r, c, et, var, chiave in ((1, 0, "x", self.v_x, "x"), (1, 2, "y", self.v_y, "y"),
                                      (2, 0, "σ y", self.v_sy, "sy"),
                                      (2, 2, "σ x", self.v_sx, "sx")):
            ttk.Label(f, text=et).grid(row=r, column=c, sticky="e", padx=(0, 4), pady=2)
            cb = ttk.Combobox(f, textvariable=var, width=15, state="disabled")
            cb.grid(row=r, column=c + 1, sticky="w", pady=2)
            cb.bind("<<ComboboxSelected>>", self.ridisegna)
            self.cb[chiave] = cb
        self.v_kev = tk.BooleanVar(value=True)
        self.ck_kev = ttk.Checkbutton(f, text="Asse x in keV (spettro calibrato)",
                                      variable=self.v_kev, command=self._cambia_unita,
                                      state="disabled")
        self.ck_kev.grid(row=3, column=0, columnspan=4, sticky="w", pady=(2, 0))
        g = ttk.Frame(f)
        g.grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.v_lo, self.v_hi = tk.StringVar(), tk.StringVar()
        ttk.Label(g, text="Intervallo x da").pack(side="left")
        for var, dopo in ((self.v_lo, "a"), (self.v_hi, "")):
            e = ttk.Entry(g, textvariable=var, width=9)
            e.pack(side="left", padx=4)
            e.bind("<Return>", self.ridisegna)
            e.bind("<FocusOut>", self.ridisegna)
            if dopo:
                ttk.Label(g, text=dopo).pack(side="left")
        ttk.Button(g, text="Tutto", command=self.tutto_intervallo).pack(side="left", padx=4)
        ttk.Label(f, text="Oppure trascina il mouse sul grafico per scegliere l'intervallo.",
                  foreground="#555").grid(row=5, column=0, columnspan=4, sticky="w")

        # ---- 2. legge
        f = ttk.LabelFrame(sin, text="2. Legge  y = f(x)", padding=6)
        f.pack(fill="x", pady=(8, 0))
        self.v_pronta = tk.StringVar(value=LIBERA)
        self.cb_pronta = cb = ttk.Combobox(f, textvariable=self.v_pronta, state="readonly",
                                           width=16, values=[LIBERA] + list(eng.LEGGI))
        cb.grid(row=0, column=0, sticky="w")
        cb.bind("<<ComboboxSelected>>", self.scegli_pronta)
        self.v_descr = tk.StringVar()
        ttk.Label(f, textvariable=self.v_descr, foreground="#555", wraplength=230).grid(
            row=0, column=1, sticky="w", padx=6)
        g = ttk.Frame(f)
        g.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Button(g, text="Aggiungi al menu…", command=self.aggiungi_legge).pack(side="left")
        ttk.Button(g, text="Modifica…", command=self.modifica_legge).pack(side="left", padx=4)
        ttk.Button(g, text="Rimuovi", command=self.rimuovi_legge).pack(side="left")
        ttk.Button(g, text="Ripristina predefinite",
                   command=self.ripristina_leggi).pack(side="left", padx=4)
        self.v_legge = tk.StringVar()
        e = ttk.Entry(f, textvariable=self.v_legge, width=52)
        e.grid(row=2, column=0, columnspan=2, sticky="we", pady=4)
        e.bind("<Return>", lambda ev: self.leggi_parametri())
        ttk.Button(f, text="Leggi parametri", command=self.leggi_parametri).grid(
            row=3, column=0, sticky="w")
        ttk.Label(f, text="Funzioni: exp log log10 sqrt sin cos tan erf erfc abs; "
                          "costante pi; potenze con ** o ^.",
                  foreground="#555", wraplength=380, justify="left").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # ---- 3. parametri
        f = ttk.LabelFrame(sin, text="3. Parametri", padding=6)
        f.pack(fill="x", pady=(8, 0))
        self.fr_par = ttk.Frame(f)
        self.fr_par.pack(fill="x")
        self._ricostruisci_parametri([])
        g = ttk.Frame(f)
        g.pack(fill="x", pady=(6, 0))
        ttk.Button(g, text="Stima automatica", command=self.stima).pack(side="left")
        ttk.Button(g, text="Anteprima curva", command=self.anteprima).pack(side="left", padx=6)
        ttk.Button(g, text="Risultati → iniziali", command=self.risultati_iniziali).pack(
            side="left")

        # ---- 4. derivate
        f = ttk.LabelFrame(sin, text="4. Grandezze derivate (facoltativo)", padding=6)
        f.pack(fill="x", pady=(8, 0))
        self.v_der = tk.StringVar()
        ttk.Entry(f, textvariable=self.v_der, width=52).pack(fill="x")
        ttk.Label(f, text="Separate da ;   es.  area=A*s*sqrt(2*pi); FWHM=2.3548*s",
                  foreground="#555").pack(anchor="w")

        # ---- azioni: sopra il grafico, cosi' restano visibili anche su schermi bassi
        g = ttk.Frame(des, padding=(6, 6, 6, 2))
        g.pack(side="top", fill="x")
        ttk.Button(g, text="Esegui fit  (F5)", command=self.esegui_fit).pack(side="left")
        ttk.Button(g, text="Salva risultati…", command=self.salva).pack(side="left", padx=6)
        self.v_log = tk.BooleanVar(value=False)
        ttk.Checkbutton(g, text="Scala log y", variable=self.v_log,
                        command=self.ridisegna).pack(side="left", padx=(14, 0))
        self.v_box = tk.BooleanVar(value=True)
        ttk.Checkbutton(g, text="Parametri sul grafico", variable=self.v_box,
                        command=self.ridisegna).pack(side="left", padx=10)

        # ---- grafico e report
        vp = ttk.PanedWindow(des, orient="vertical")
        vp.pack(fill="both", expand=True)
        alto, basso = ttk.Frame(vp), ttk.Frame(vp, padding=(6, 4))
        vp.add(alto, weight=3)
        vp.add(basso, weight=1)
        self.fig = Figure(figsize=(7.5, 5.2), dpi=100, constrained_layout=True)
        gs = self.fig.add_gridspec(2, 1, height_ratios=[3, 1])
        self.ax = self.fig.add_subplot(gs[0])
        self.axr = self.fig.add_subplot(gs[1], sharex=self.ax)
        self.canvas = FigureCanvasTkAgg(self.fig, master=alto)
        barra = NavigationToolbar2Tk(self.canvas, alto)
        barra.update()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        basso.rowconfigure(0, weight=1)
        basso.columnconfigure(0, weight=1)
        self.txt = tk.Text(basso, height=13, wrap="none",
                           font=tkfont.nametofont("TkFixedFont"))
        self.txt.grid(row=0, column=0, sticky="nsew")
        sv = ttk.Scrollbar(basso, orient="vertical", command=self.txt.yview)
        sv.grid(row=0, column=1, sticky="ns")
        so = ttk.Scrollbar(basso, orient="horizontal", command=self.txt.xview)
        so.grid(row=1, column=0, sticky="we")
        self.txt.configure(yscrollcommand=sv.set, xscrollcommand=so.set)
        ttk.Button(basso, text="Copia report", command=self.copia).grid(
            row=2, column=0, sticky="w", pady=(4, 0))

    def _ricostruisci_parametri(self, names):
        for w in self.widget_par:
            w.destroy()
        self.widget_par = []
        vecchie, self.righe = self.righe, {}
        # i valori si conservano solo se la legge e' stata ritoccata (termini
        # aggiunti o tolti); con una legge diversa si riparte da zero, cosi' un
        # parametro omonimo non eredita valori, limiti o il segno di fisso
        if not (set(names) >= set(vecchie) or set(names) <= set(vecchie)):
            vecchie = {}
        if not names:
            w = ttk.Label(self.fr_par, foreground="#555",
                          text="Scrivi la legge e premi Leggi parametri.")
            w.grid(row=0, column=0, sticky="w")
            self.widget_par.append(w)
            return
        for c, et in enumerate(("parametro", "valore iniziale", "minimo", "massimo", "fisso")):
            w = ttk.Label(self.fr_par, text=et, foreground="#555")
            w.grid(row=0, column=c, sticky="w", padx=3)
            self.widget_par.append(w)
        for r, n in enumerate(names, start=1):
            riga = vecchie.get(n) or {"val": tk.StringVar(), "lo": tk.StringVar(),
                                      "hi": tk.StringVar(), "fix": tk.BooleanVar(value=False)}
            self.righe[n] = riga
            w = ttk.Label(self.fr_par, text=n, width=10)
            w.grid(row=r, column=0, sticky="w", padx=3, pady=1)
            self.widget_par.append(w)
            for c, k, larg in ((1, "val", 14), (2, "lo", 9), (3, "hi", 9)):
                w = ttk.Entry(self.fr_par, textvariable=riga[k], width=larg)
                w.grid(row=r, column=c, padx=3, pady=1)
                self.widget_par.append(w)
            w = ttk.Checkbutton(self.fr_par, variable=riga["fix"])
            w.grid(row=r, column=4, padx=3)
            self.widget_par.append(w)

    # ------------------------------------------------------------ utilita'
    def stato(self, testo):
        self.v_stato.set(testo)

    def mostra_testo(self, testo):
        self.testo = testo
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", testo)

    def errore(self, titolo, e):
        messagebox.showerror(titolo, str(e))
        self.stato(f"{titolo}: {e}")

    # ------------------------------------------------------------ dati
    def apri_dialogo(self):
        path = filedialog.askopenfilename(
            title="Apri dati",
            filetypes=[("Dati e spettri", "*.csv *.txt *.dat *.tsv *.Spe *.spe *.SPE"),
                       ("Tutti i file", "*.*")])
        if path:
            self.apri(path)

    def apri(self, path):
        try:
            d = Dati(path)
        except (OSError, ValueError) as e:
            self.errore("File non leggibile", e)
            return
        self.dati, self.ris, self.ante = d, None, None
        self.v_file.set(d.nome)
        self.v_lo.set("")
        self.v_hi.set("")
        if d.spe:
            for k in ("x", "y", "sx"):
                self.cb[k].configure(state="disabled")
            self.v_x.set("canale / energia")
            self.v_y.set("conteggi")
            self.v_sx.set(NESSUNA)
            self.cb["sy"]["values"] = [POISSON, NESSUNA]
            self.cb["sy"].configure(state="readonly")
            self.v_sy.set(POISSON)
            self.ck_kev.configure(state="normal" if d.cal else "disabled")
            self.v_kev.set(bool(d.cal))
            self.stato(f"{d.nome}: {len(d.counts)} canali, live time {d.lt:g} s, "
                       + ("calibrato in energia." if d.cal else "non calibrato (asse in canali)."))
        else:
            et = d.etichette
            for k, valori in (("x", et), ("y", et), ("sy", [NESSUNA, POISSON] + et),
                              ("sx", [NESSUNA] + et)):
                self.cb[k]["values"] = valori
                self.cb[k].configure(state="readonly")
            self.v_x.set(et[0])
            self.v_y.set(et[1])
            terza = len(et) >= 3 and bool(np.all(d.arr[:, 2] > 0))
            self.v_sy.set(et[2] if terza else NESSUNA)
            self.v_sx.set(NESSUNA)
            self.ck_kev.configure(state="disabled")
            self.stato(f"{d.nome}: {d.arr.shape[0]} righe, {d.arr.shape[1]} colonne."
                       + (f" Ho preso {et[2]} come σ y: controlla che sia giusto." if terza
                          else " Nessuna σ y selezionata."))
        self.mostra_testo("")
        self.ridisegna()

    def _cambia_unita(self):
        self.v_lo.set("")
        self.v_hi.set("")
        self.ridisegna()

    def tutto_intervallo(self):
        self.v_lo.set("")
        self.v_hi.set("")
        self.ridisegna()

    def corrente(self):
        """Dati secondo le scelte correnti, con la maschera dell'intervallo."""
        if self.dati is None:
            return None
        x, y, sy, sx, xl, yl = self.dati.estrai(self.v_x.get(), self.v_y.get(),
                                                self.v_sy.get(), self.v_sx.get(),
                                                self.v_kev.get())
        lo, hi = num(self.v_lo.get()), num(self.v_hi.get())
        if lo is not None and hi is not None and lo > hi:
            lo, hi = hi, lo
        m = np.ones(len(x), bool)
        if lo is not None:
            m &= x >= lo
        if hi is not None:
            m &= x <= hi
        firma = (self.dati.path, self.v_x.get(), self.v_y.get(), self.v_sy.get(),
                 self.v_sx.get(), self.v_kev.get(), lo, hi)
        return {"x": x, "y": y, "sy": sy, "sx": sx, "xl": xl, "yl": yl, "m": m,
                "lo": lo, "hi": hi, "firma": firma}

    # ------------------------------------------------------------ legge
    def scegli_pronta(self, *_):
        nome = self.v_pronta.get()
        if nome in eng.LEGGI:
            self.v_legge.set(eng.LEGGI[nome][0])
            self.v_descr.set(eng.LEGGI[nome][1])
            self.righe = {}                      # legge pronta: tabella nuova
            self.leggi_parametri()
        else:
            self.v_descr.set("")

    # ------------------------------------------------------------ menu leggi
    def _applica_leggi(self, nuove):
        """Salva su file e aggiorna menu e motore; False se il salvataggio fallisce."""
        try:
            salva_leggi(nuove)
        except OSError as e:
            self.errore("Non riesco a salvare le leggi", e)
            return False
        imposta_leggi(nuove)
        self.cb_pronta["values"] = [LIBERA] + list(eng.LEGGI)
        return True

    def _seleziona(self, nome):
        """Mostra nel menu la legge appena salvata, senza azzerare i valori dei
        parametri gia' scritti se la legge ha gli stessi parametri."""
        self.v_pronta.set(nome)
        self.v_legge.set(eng.LEGGI[nome][0])
        self.v_descr.set(eng.LEGGI[nome][1])
        self.leggi_parametri()

    def aggiungi_legge(self):
        d = DialogoLegge(self.root, "Aggiungi legge al menu", legge=self.v_legge.get().strip())
        if d.risultato is None:
            return
        nome, legge, descr = d.risultato
        if self._applica_leggi(leggi_con(eng.LEGGI, nome, legge, descr)):
            self._seleziona(nome)
            self.stato(f"Legge '{nome}' aggiunta al menu.")

    def modifica_legge(self):
        vecchio = self.v_pronta.get()
        if vecchio not in eng.LEGGI:
            self.stato("Scegli prima dal menu la legge da modificare.")
            return
        legge, descr = eng.LEGGI[vecchio]
        d = DialogoLegge(self.root, f"Modifica legge '{vecchio}'", nome=vecchio, legge=legge,
                         descr=descr, vecchio=vecchio)
        if d.risultato is None:
            return
        nome, legge, descr = d.risultato
        if self._applica_leggi(leggi_con(eng.LEGGI, nome, legge, descr, vecchio)):
            self._seleziona(nome)
            self.stato(f"Legge '{nome}' modificata." if nome == vecchio
                       else f"Legge '{vecchio}' modificata e rinominata in '{nome}'.")

    def rimuovi_legge(self):
        nome = self.v_pronta.get()
        if nome not in eng.LEGGI:
            self.stato("Scegli prima dal menu la legge da rimuovere.")
            return
        if not messagebox.askyesno("Rimuovi legge", f"Togliere '{nome}' dal menu?\n"
                                   "L'espressione resta nella casella della legge."):
            return
        if self._applica_leggi({k: v for k, v in eng.LEGGI.items() if k != nome}):
            self.v_pronta.set(LIBERA)
            self.v_descr.set("")
            self.stato(f"Legge '{nome}' rimossa dal menu.")

    def ripristina_leggi(self):
        if not messagebox.askyesno("Ripristina predefinite",
                                   "Il menu tornerà alle leggi predefinite: quelle aggiunte "
                                   "e le modifiche andranno perse. Continuare?"):
            return
        if self._applica_leggi(dict(PREDEFINITE)):
            if self.v_pronta.get() not in eng.LEGGI:
                self.v_pronta.set(LIBERA)
            nome = self.v_pronta.get()
            self.v_descr.set(eng.LEGGI[nome][1] if nome in eng.LEGGI else "")
            self.stato("Menu delle leggi riportato alle leggi predefinite.")

    def leggi_parametri(self, silenzioso=False):
        """Riconosce i parametri della legge e aggiorna la tabella."""
        try:
            _, names, _, _ = eng.parse_law(self.v_legge.get())
        except ValueError as e:
            if not silenzioso:
                self.errore("Legge non valida", e)
            return None
        if names != list(self.righe):
            self._ricostruisci_parametri(names)
            self.ante = None
            if not silenzioso:
                self.stato("Parametri: " + ", ".join(names)
                           + ". I valori iniziali lasciati vuoti vengono stimati.")
        return names

    def tabella(self):
        out = {}
        for n, r in self.righe.items():
            valori = []
            for k, et in (("val", "valore iniziale"), ("lo", "minimo"), ("hi", "massimo")):
                try:
                    valori.append(num(r[k].get()))
                except ValueError:
                    raise ValueError(f"{et} di {n} non è un numero: '{r[k].get()}'")
            out[n] = (valori[0], valori[1], valori[2], bool(r["fix"].get()))
        return out

    def _pronto(self):
        """Controlli comuni prima di stima, anteprima e fit."""
        if self.dati is None:
            raise ValueError("apri prima un file di dati")
        if not self.v_legge.get().strip():
            raise ValueError("scrivi una legge, per esempio a + b*x")
        names = self.leggi_parametri(silenzioso=True)
        if names is None:
            eng.parse_law(self.v_legge.get())        # rilancia l'errore con il messaggio
        d = self.corrente()
        if d["m"].sum() < 2:
            raise ValueError("meno di due punti nell'intervallo scelto")
        return names, d

    def stima(self):
        try:
            names, d = self._pronto()
            m = d["m"]
            g = eng.guess_p0(names, d["x"][m], d["y"][m], {})
        except Exception as e:
            self.errore("Stima non riuscita", e)
            return
        for n, v in zip(names, g):
            if not self.righe[n]["fix"].get():
                self.righe[n]["val"].set(f"{v:.6g}")
        self.stato("Valori iniziali stimati dai dati nell'intervallo. Controllali con Anteprima curva.")

    def anteprima(self):
        try:
            names, d = self._pronto()
            tab = self.tabella()
            m = d["m"]
            utente = {n: tab[n][0] for n in names if tab[n][0] is not None}
            p = eng.guess_p0(names, d["x"][m], d["y"][m], utente)
            _, _, f, _ = eng.parse_law(self.v_legge.get())
            fs = eng._safe(f)
        except Exception as e:
            self.errore("Anteprima non riuscita", e)
            return
        self.ante = lambda xs: fs(np.asarray(xs, float), *p)
        self.ridisegna()
        self.stato("Anteprima con i valori iniziali (curva tratteggiata). "
                   "Se è lontana dai dati, correggi i valori prima del fit.")

    def risultati_iniziali(self):
        if not self.ris:
            self.stato("Nessun fit da cui prendere i valori.")
            return
        for n, v in zip(self.ris["names"], self.ris["p"]):
            if n in self.righe:
                self.righe[n]["val"].set(f"{v:.6g}")
        self.stato("I risultati del fit sono ora i valori iniziali.")

    # ------------------------------------------------------------ fit
    def esegui_fit(self):
        try:
            names, d = self._pronto()
            m = d["m"]
            sel = lambda a: None if a is None else a[m]
            intervallo = ""
            if d["lo"] is not None or d["hi"] is not None:
                intervallo = f" [{d['x'][m].min():g}, {d['x'][m].max():g}]"
            self.root.configure(cursor="watch")
            self.root.update_idletasks()
            try:
                ris = calcola_fit(self.v_legge.get(), self.tabella(), d["x"][m], d["y"][m],
                                  sel(d["sy"]), sel(d["sx"]), self.v_der.get(),
                                  self.dati.nome + intervallo)
            finally:
                self.root.configure(cursor="")
        except Exception as e:
            self.errore("Fit non riuscito", e)
            return
        ris["firma"] = d["firma"]
        self.ris, self.ante = ris, None
        self.mostra_testo(ris["testo"])
        self.ridisegna()
        R = ris["R"]
        if R["weighted"]:
            self.stato(f"Fit completato: χ² = {R['chi2']:.4g} con {R['ndof']} gradi di libertà "
                       f"(χ² ridotto {R['chi2r']:.3g}, p-value {R['pval']:.3g}).")
        else:
            self.stato("Fit completato senza σ sui dati: incertezze stimate dai residui, "
                       "χ² non calcolabile.")

    # ------------------------------------------------------------ grafico
    def ridisegna(self, *_):
        ax, axr = self.ax, self.axr
        if self.span is not None:
            self.span.disconnect_events()
            self.span = None
        ax.clear()
        axr.clear()
        try:
            d = self.corrente()
        except ValueError as e:
            self.stato(f"Intervallo non valido: {e}")
            d = None
        if d is None:
            ax.text(0.5, 0.5, "Apri un file di dati", ha="center", va="center",
                    transform=ax.transAxes, color="0.5")
            ax.set_xticks([]); ax.set_yticks([])
            axr.set_xticks([]); axr.set_yticks([])
            self.canvas.draw_idle()
            return
        x, y, sy, sx, m = d["x"], d["y"], d["sy"], d["sx"], d["m"]
        if self.ris and self.ris.get("firma") != d["firma"]:
            self.ris = None
            self.stato("Dati o intervallo cambiati: riesegui il fit.")
        if not m.any():
            self.stato("Nessun punto nell'intervallo scelto.")

        if (~m).any():
            ax.plot(x[~m], y[~m], ".", color="0.72", ms=3, label="fuori intervallo")
        if m.any():
            if m.sum() <= 600:
                ax.errorbar(x[m], y[m], yerr=None if sy is None else sy[m],
                            xerr=None if sx is None else sx[m], fmt="o", ms=3, lw=0.8,
                            color="C0", label="dati")
            else:
                ax.plot(x[m], y[m], ".", color="C0", ms=3, label="dati")

        # limiti in x: tutto, oppure l'intervallo con un margine
        x0, x1 = float(x.min()), float(x.max())
        if m.any() and (d["lo"] is not None or d["hi"] is not None):
            a, b = float(x[m].min()), float(x[m].max())
            w = (b - a) or 1.0
            v0, v1 = max(x0, a - 0.25 * w), min(x1, b + 0.25 * w)
        else:
            v0, v1 = x0, x1
        marg = 0.02 * ((v1 - v0) or 1.0)
        v0, v1 = v0 - marg, v1 + marg
        xs = np.linspace(x[m].min(), x[m].max(), 800) if m.any() else None
        riquadro = None

        if self.ante is not None and xs is not None:
            ax.plot(xs, self.ante(xs), "--", color="C1", lw=1.3, label="valori iniziali")
        if self.ris and xs is not None:
            R = self.ris["R"]
            ax.plot(xs, self.ris["curva"](xs), "-", color="C3", lw=1.6, label="fit")
            if R["weighted"]:
                axr.errorbar(x[m], R["res"] / R["s_eff"], yerr=1, fmt="o", ms=3, lw=0.8,
                             color="C0")
                axr.axhspan(-2, 2, color="0.9", zorder=0)
                axr.set_ylabel("residui / σ")
            else:
                axr.plot(x[m], R["res"], "o", ms=3, color="C0")
                axr.set_ylabel("residui")
            if self.v_box.get():
                riquadro = [f"{n} = {eng.fmt_val(v, e)}" for n, v, e in
                            zip(self.ris["liberi"], R["p"], R["perr"])]
                riquadro += [f"{n} = {v:.6g} (fisso)" for n, v in self.ris["fissi"].items()]
                if R["weighted"]:
                    riquadro.append(f"χ²/ndf = {R['chi2']:.1f}/{R['ndof']}")
        else:
            axr.set_ylabel("residui")
        axr.axhline(0, color="C3", lw=1)

        # limiti in y sui punti visibili
        vis = (x >= v0) & (x <= v1)
        if vis.any():
            alto = y[vis] + (sy[vis] if sy is not None else 0)
            basso = y[vis] - (sy[vis] if sy is not None else 0)
            if self.v_log.get():
                pos = y[vis][y[vis] > 0]
                if len(pos):
                    ax.set_yscale("log")
                    ax.set_ylim(pos.min() * 0.6, max(alto.max(), pos.max()) * 1.8)
                else:
                    self.stato("Scala log non applicabile: nessun valore positivo.")
            else:
                h = (alto.max() - basso.min()) or 1.0
                ax.set_ylim(basso.min() - 0.05 * h, alto.max() + 0.10 * h)
        ax.set_xlim(v0, v1)
        ax.set_ylabel(d["yl"])
        axr.set_xlabel(d["xl"])
        ax.tick_params(labelbottom=False)

        # legenda a destra e riquadro a sinistra, in alto o in basso secondo
        # dove i dati lasciano spazio
        def dati_in_alto(lato):
            q = v0 + 0.3 * (v1 - v0) if lato == "sin" else v1 - 0.3 * (v1 - v0)
            sel = vis & ((x <= q) if lato == "sin" else (x >= q))
            if not sel.any():
                return False
            y0, y1 = ax.get_ylim()
            val = float(np.median(y[sel]))
            if ax.get_yscale() == "log":
                if val <= 0:
                    return False
                return (np.log(val) - np.log(y0)) / (np.log(y1) - np.log(y0)) > 0.5
            return (val - y0) / ((y1 - y0) or 1.0) > 0.5
        ax.legend(loc="lower right" if dati_in_alto("des") else "upper right", fontsize=8)
        if riquadro:
            giu = dati_in_alto("sin")
            ax.text(0.015, 0.03 if giu else 0.97, "\n".join(riquadro),
                    transform=ax.transAxes, va="bottom" if giu else "top", fontsize=8,
                    family="monospace", bbox=dict(fc="white", alpha=0.85, lw=0.5))

        def scelto(a, b):
            if b - a > 0:
                self.v_lo.set(f"{a:.6g}")
                self.v_hi.set(f"{b:.6g}")
                self.root.after_idle(self.ridisegna)
        try:
            self.span = SpanSelector(ax, scelto, "horizontal", useblit=False,
                                     props=dict(alpha=0.18, facecolor="C0"))
        except TypeError:                                   # matplotlib < 3.5
            self.span = SpanSelector(ax, scelto, "horizontal", useblit=False,
                                     rectprops=dict(alpha=0.18, facecolor="C0"))
        self.canvas.draw_idle()

    # ------------------------------------------------------------ uscite
    def copia(self):
        if not self.testo:
            self.stato("Nessun report da copiare.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.testo)
        self.stato("Report copiato negli appunti.")

    def salva(self):
        if not self.ris:
            self.stato("Esegui prima un fit: non c'è ancora nulla da salvare.")
            return
        base = os.path.splitext(self.dati.nome)[0] + "_fit.png"
        path = filedialog.asksaveasfilename(title="Salva risultati", initialfile=base,
                                            defaultextension=".png",
                                            filetypes=[("Grafico PNG", "*.png")])
        if not path:
            return
        radice = os.path.splitext(path)[0]
        try:
            d = self.corrente()
            m, R = d["m"], self.ris["R"]
            self.fig.savefig(radice + ".png", dpi=150)
            with open(radice + "_report.txt", "w", encoding="utf-8") as fh:
                fh.write(self.testo + "\n")
            col = [d["x"][m], d["y"][m]]
            intest = ["x", "y"]
            if R["s_eff"] is not None:
                col.append(R["s_eff"])
                intest.append("sigma")
            col += [R["yfit"], R["res"]]
            intest += ["y_fit", "residuo"]
            np.savetxt(radice + "_punti.csv", np.column_stack(col), delimiter=",",
                       header=",".join(intest), comments="", fmt="%.8g")
        except Exception as e:
            self.errore("Salvataggio non riuscito", e)
            return
        self.stato(f"Salvati {os.path.basename(radice)}.png, _report.txt e _punti.csv "
                   f"in {os.path.dirname(radice) or '.'}")


def main():
    root = tk.Tk()
    App(root, sys.argv[1] if len(sys.argv) > 1 else None)
    root.mainloop()


if __name__ == "__main__":
    main()
