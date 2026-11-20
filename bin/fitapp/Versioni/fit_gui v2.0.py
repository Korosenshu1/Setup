#!/usr/bin/env python3
"""
fit_gui.py - Interfaccia grafica per il fit di dati con una legge scritta a mano.

Usa il motore di calcolo di fit_legge.py, che deve stare nella stessa cartella.

Avvio:   python fit_gui.py            (oppure: python fit_gui.py dati.csv)

Cosa si puo' fare:
  - aprire file a colonne (.csv .txt .dat; separatore e virgola decimale
    riconosciuti da soli) o spettri MAESTRO .Spe;
  - scegliere le colonne di x e y (o il numero di riga come x);
  - per σ y e σ x scegliere una colonna, una formula del menu degli errori
    (es. poissoniano √y, 1% del valore) o scrivere una formula in x, y e
    nelle colonne c0, c1, ...; le formule del menu si aggiungono, modificano,
    rinominano e rimuovono con "Formule errori…" (errori_utente.json);
  - usare le σ come pesi relativi (incertezze scalate con √χ² ridotto);
  - scegliere l'intervallo del fit trascinando il mouse sul grafico;
  - scrivere la legge in funzione di x, o sceglierne una gia' pronta;
  - gestire il menu delle leggi pronte: aggiungerne con un nome a scelta,
    modificarle, rinominarle, rimuoverle o ripristinare quelle predefinite
    (salvate in leggi_utente.json accanto a questo file);
  - dare valori iniziali e limiti ai parametri, oppure fissarli;
  - vedere in anteprima la curva con i valori iniziali;
  - ottenere parametri, incertezze, chi quadro, correlazioni, residui e
    grandezze derivate con l'incertezza propagata;
  - scala logaritmica su x e su y;
  - salvare grafico (.png), report (.txt) e tabella dei punti (.csv);
  - rifare esattamente un fit da un report salvato ("Riapri da report…"): il
    report contiene in fondo tutte le impostazioni; il file dei dati viene
    cercato dov'era o nella cartella del report, e alla fine i parametri sono
    confrontati con quelli registrati.

Tasti: Ctrl+O apre un file, Ctrl+R riapre da report, F5 esegue il fit.

Dipendenze: numpy, scipy, sympy, matplotlib, tkinter (incluso in Python su
Windows e macOS; su Linux Debian/Ubuntu: sudo apt install python3-tk).
"""
import os
import re
import sys

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
FORMULA = "(formula)"
LIBERA = "(scrivi la tua)"
INDICE = "n° di riga (0, 1, 2…)"
RISERVATI = {NESSUNA, FORMULA, LIBERA, INDICE}


# ==========================================================================
# Logica indipendente dall'interfaccia
# ==========================================================================
def num(testo, default=None):
    """Numero da una casella di testo; accetta la virgola decimale."""
    t = str(testo).strip().replace(",", ".")
    if not t:
        return default
    return float(t)


def controlla_legge(nome, legge):
    """Solleva ValueError se nome o espressione della legge non vanno bene."""
    if not nome:
        raise ValueError("dai un nome alla legge")
    if nome in RISERVATI:
        raise ValueError(f"il nome '{nome}' è riservato")
    if not legge:
        raise ValueError("scrivi l'espressione della legge")
    if legge in eng.LEGGI:
        raise ValueError("scrivi l'espressione della legge, non il nome di una legge del menu")
    eng.parse_law(legge)                              # ValueError se non valida


def controlla_errore(nome, formula):
    """Solleva ValueError se nome o formula dell'incertezza non vanno bene."""
    if not nome:
        raise ValueError("dai un nome alla formula")
    if nome in RISERVATI or re.match(r"col \d+", nome):
        raise ValueError(f"il nome '{nome}' è riservato")
    eng.compila_formula(formula)                      # ValueError se non valida


def _norm(s):
    """Nome di colonna senza unita' di misura ([s], (mV)), spazi e segni."""
    s = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", s.lower())
    return re.sub(r"[\s_\-.:/]", "", s)


def trova_colonna_errore(nomi, i):
    """Indice della colonna d'intestazione che sembra l'errore della colonna i
    (es. 'dy', 'sigma_y', 'err y', 'y_err', 'σV' per 'V'), oppure None."""
    if not nomi:
        return None
    t = _norm(nomi[i])
    if not t:
        return None
    prefissi = ("sigma", "sig", "errore", "err", "incertezza", "inc", "unc", "delta",
                "σ", "δ", "d", "s", "e", "u")
    suffissi = ("err", "errore", "sigma", "sig", "unc", "inc")
    for j, nm in enumerate(nomi):
        if j == i:
            continue
        n = _norm(nm)
        if any(n == p + t for p in prefissi) or any(n == t + s for s in suffissi):
            return j
    return None


class Dati:
    """Un file caricato: tabella a colonne oppure spettro .Spe."""

    def __init__(self, path):
        self.path = path
        self.nome = os.path.basename(path)
        self.spe = path.lower().endswith(".spe")
        if self.spe:
            info = eng.read_spe_full(path)
            self.counts, self.cal, self.lt = info["counts"], info["cal"], info["lt"]
            self.primo, self.unita = info["primo"], info["unita"]
            self.etichette, self.nomi, self.info = [], None, info
        else:
            self.info = eng.read_table(path)
            self.arr, self.nomi = self.info["arr"], self.info["nomi"]
            self.etichette = [f"col {i}" + (f": {self.nomi[i]}" if self.nomi else "")
                              for i in range(self.arr.shape[1])]

    def variabili_formula(self):
        """Testo d'aiuto: nomi utilizzabili nelle formule degli errori."""
        if self.spe:
            return "x, y (conteggi), ch (canale)"
        extra = [nm for nm in eng.variabili_tabella(self.arr, self.nomi, None, None)
                 if nm not in ("x", "y") and not re.fullmatch(r"c\d+", nm)]
        cols = f"c0…c{self.arr.shape[1] - 1}" if self.arr.shape[1] > 1 else "c0"
        return "x, y, " + cols + (", " + ", ".join(extra) if extra else "")

    def estrai(self, x_et, y_et, sy_sel, sy_form, sx_sel, sx_form, kev=True):
        """Restituisce x, y, sigma_y, sigma_x, etichetta x, etichetta y e un
        eventuale messaggio d'errore sulle formule delle sigma."""
        if self.spe:
            ch = self.primo + np.arange(len(self.counts), dtype=float)
            usa_e = bool(kev and self.cal)
            x = sum(c * ch**k for k, c in enumerate(self.cal)) if usa_e else ch
            y = self.counts
            var = {"x": x, "y": y, "ch": ch}
            xl, yl = (f"Energia [{self.unita}]" if usa_e else "Canale"), "Conteggi"
            colonna = None
        else:
            idx = self.etichette.index
            x = (np.arange(len(self.arr), dtype=float) if x_et == INDICE
                 else self.arr[:, idx(x_et)])
            y = self.arr[:, idx(y_et)]
            var = eng.variabili_tabella(self.arr, self.nomi, x, y)
            colonna = lambda et: self.arr[:, idx(et)].astype(float)
            nome = lambda et: et.split(": ", 1)[1] if ": " in et else et
            xl = "n° di riga" if x_et == INDICE else nome(x_et)
            yl = nome(y_et)
        problemi = []

        def sigma(sel, formula, et):
            if not sel or sel == NESSUNA:
                return None
            if colonna is not None and sel in self.etichette:
                return colonna(sel)
            try:
                return eng.valuta_formula(formula, var, len(x))
            except ValueError as e:
                problemi.append(f"{et}: {e}")
                return None
        sy = sigma(sy_sel, sy_form, "σ y")
        sx = sigma(sx_sel, sx_form, "σ x")
        return x, y, sy, sx, xl, yl, ("; ".join(problemi) or None)


# Il fit e' quello del motore: stesso risultato da GUI e da riga di comando.
calcola_fit = eng.fit_tabella


# ==========================================================================
# Interfaccia
# ==========================================================================
class DialogoVoce(tk.Toplevel):
    """Finestra per scrivere nome, testo (legge o formula) e descrizione di una
    voce di menu. Dopo la chiusura, self.risultato e' (nome, testo, descrizione)
    oppure None."""

    def __init__(self, parent, titolo, etichetta, menu, controlla, nome="", testo="",
                 descr="", vecchio=None, nota=""):
        super().__init__(parent)
        self.title(titolo)
        self.transient(parent)
        self.resizable(True, False)
        self.menu, self.controlla, self.vecchio = menu, controlla, vecchio
        self.risultato = None
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        self.v_nome, self.v_testo, self.v_descr = (tk.StringVar(value=nome),
                                                   tk.StringVar(value=testo),
                                                   tk.StringVar(value=descr))
        campi = (("Nome nel menu", self.v_nome, 24, "w"),
                 (etichetta, self.v_testo, 64, "we"),
                 ("Descrizione", self.v_descr, 64, "we"))
        for r, (et, var, larg, sticky) in enumerate(campi):
            ttk.Label(f, text=et).grid(row=r, column=0, sticky="e", padx=(0, 6), pady=3)
            e = ttk.Entry(f, textvariable=var, width=larg)
            e.grid(row=r, column=1, sticky=sticky, pady=3)
            if r == 0:
                e.focus_set()
                e.select_range(0, "end")
        if nota:
            ttk.Label(f, text=nota, foreground="#555", wraplength=520, justify="left").grid(
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
        nome, testo = self.v_nome.get().strip(), self.v_testo.get().strip()
        descr = self.v_descr.get().strip()
        try:
            self.controlla(nome, testo)
        except ValueError as e:
            messagebox.showerror("Voce non valida", str(e), parent=self)
            return
        if nome != self.vecchio and nome in self.menu:
            if not messagebox.askyesno("Nome già usato",
                                       f"Nel menu c'è già '{nome}'.\nVuoi sostituirla?",
                                       parent=self):
                return
        self.risultato = (nome, testo, descr)
        self.destroy()


NOTA_ERRORI = ("Variabili: x e y (le colonne scelte), le colonne c0, c1, … o il loro nome "
               "d'intestazione; per gli spettri anche ch (canale). Funzioni: sqrt exp log "
               "log10 abs max min sin cos tan; costante pi. Esempi: 0.05*y   "
               "sqrt(c2**2 + (0.01*y)**2)   max(sqrt(y), 1)   0.5")


class GestoreErrori(tk.Toplevel):
    """Elenco delle formule degli errori con aggiunta, modifica e rimozione."""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Formule degli errori")
        self.transient(app.root)
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)
        self.lista = tk.Listbox(f, height=10, width=72, exportselection=False,
                                font=tkfont.nametofont("TkFixedFont"))
        self.lista.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(f, orient="vertical", command=self.lista.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.lista.configure(yscrollcommand=sb.set)
        self.v_descr = tk.StringVar()
        ttk.Label(f, textvariable=self.v_descr, foreground="#555", wraplength=560).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        b = ttk.Frame(f)
        b.grid(row=0, column=2, rowspan=2, sticky="n", padx=(8, 0))
        for testo, cmd in (("Aggiungi…", self.aggiungi), ("Modifica…", self.modifica),
                           ("Rimuovi", self.rimuovi), ("Ripristina predefinite", self.ripristina),
                           ("Chiudi", self.chiudi)):
            ttk.Button(b, text=testo, command=cmd).pack(fill="x", pady=2)
        self.lista.bind("<<ListboxSelect>>", lambda e: self._mostra_descr())
        self.lista.bind("<Double-Button-1>", lambda e: self.modifica())
        self.protocol("WM_DELETE_WINDOW", self.chiudi)
        self.aggiorna()

    def chiudi(self):
        self.app.gestore = None
        self.destroy()

    def aggiorna(self, seleziona=None):
        self.nomi = list(eng.ERRORI)
        self.lista.delete(0, "end")
        for n in self.nomi:
            self.lista.insert("end", f"{n:<24s} σ = {eng.ERRORI[n][0]}")
        if seleziona in self.nomi:
            i = self.nomi.index(seleziona)
            self.lista.selection_set(i)
            self.lista.see(i)
        self._mostra_descr()

    def _scelto(self):
        s = self.lista.curselection()
        return self.nomi[s[0]] if s else None

    def _mostra_descr(self):
        n = self._scelto()
        self.v_descr.set(eng.ERRORI[n][1] if n else "")

    def aggiungi(self):
        d = DialogoVoce(self, "Aggiungi formula degli errori", "σ =", eng.ERRORI,
                        controlla_errore, testo=self.app.formula_proposta(), nota=NOTA_ERRORI)
        if d.risultato and self.app._applica_errori(eng.menu_con(eng.ERRORI, *d.risultato)):
            self.aggiorna(d.risultato[0])
            self.app.stato(f"Formula '{d.risultato[0]}' aggiunta al menu degli errori.")

    def modifica(self):
        vecchio = self._scelto()
        if vecchio is None:
            return
        formula, descr = eng.ERRORI[vecchio]
        d = DialogoVoce(self, f"Modifica formula '{vecchio}'", "σ =", eng.ERRORI,
                        controlla_errore, nome=vecchio, testo=formula, descr=descr,
                        vecchio=vecchio, nota=NOTA_ERRORI)
        if d.risultato is None:
            return
        nome = d.risultato[0]
        if self.app._applica_errori(eng.menu_con(eng.ERRORI, *d.risultato, vecchio),
                                    rinomina=(vecchio, nome)):
            self.aggiorna(nome)
            self.app.stato(f"Formula '{nome}' modificata.")

    def rimuovi(self):
        nome = self._scelto()
        if nome is None:
            return
        if not messagebox.askyesno("Rimuovi formula", f"Togliere '{nome}' dal menu?\n"
                                   "Se è in uso, la formula resta nella casella.", parent=self):
            return
        if self.app._applica_errori({k: v for k, v in eng.ERRORI.items() if k != nome}):
            self.aggiorna()
            self.app.stato(f"Formula '{nome}' rimossa dal menu degli errori.")

    def ripristina(self):
        if not messagebox.askyesno("Ripristina predefinite",
                                   "Il menu degli errori tornerà alle formule predefinite: "
                                   "quelle aggiunte e le modifiche andranno perse. Continuare?",
                                   parent=self):
            return
        if self.app._applica_errori(dict(eng.PREDEFINITE_ERRORI)):
            self.aggiorna()
            self.app.stato("Menu degli errori riportato alle formule predefinite.")


class App:
    def __init__(self, root, path=None):
        self.root = root
        root.title("Fit di dati con legge libera")
        root.geometry("1280x800")
        root.minsize(1000, 640)
        self.dati = None          # file caricato
        self.ris = None           # ultimo fit
        self.ante = None          # funzione di anteprima con i valori iniziali
        self.testo = ""           # testo del report mostrato
        self.righe = {}           # nome -> variabili della riga del parametro
        self.widget_par = []
        self.span = None
        self.gestore = None       # finestra delle formule degli errori
        avvisi = eng.carica_menu_utente()
        self._costruisci()
        root.bind("<Control-o>", lambda e: self.apri_dialogo())
        root.bind("<F5>", lambda e: self.esegui_fit())
        root.bind("<Control-r>", lambda e: self.riapri_da_report())
        self.ridisegna()
        if avvisi:
            self.stato("; ".join(avvisi) + ": uso le voci predefinite. Il file verrà "
                       "riscritto alla prossima modifica del menu.")
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
        self.cb = {}
        for c, et, var, chiave in ((0, "x", self.v_x, "x"), (2, "y", self.v_y, "y")):
            ttk.Label(f, text=et).grid(row=1, column=c, sticky="e", padx=(0, 4), pady=2)
            cb = ttk.Combobox(f, textvariable=var, width=15, state="disabled")
            cb.grid(row=1, column=c + 1, sticky="w", pady=2)
            cb.bind("<<ComboboxSelected>>", self.ridisegna)
            self.cb[chiave] = cb
        # sigma: menu (nessuna / colonna / formula del menu / formula libera) + formula
        self.v_sel = {"sy": tk.StringVar(value=NESSUNA), "sx": tk.StringVar(value=NESSUNA)}
        self.v_form = {"sy": tk.StringVar(), "sx": tk.StringVar()}
        for r, et, chiave in ((2, "σ y", "sy"), (3, "σ x", "sx")):
            ttk.Label(f, text=et).grid(row=r, column=0, sticky="e", padx=(0, 4), pady=2)
            cb = ttk.Combobox(f, textvariable=self.v_sel[chiave], width=15, state="readonly",
                              values=self._valori_sigma())
            cb.grid(row=r, column=1, sticky="w", pady=2)
            cb.bind("<<ComboboxSelected>>", lambda e, k=chiave: self._scelta_sigma(k))
            self.cb[chiave] = cb
            e = ttk.Entry(f, textvariable=self.v_form[chiave], width=24)
            e.grid(row=r, column=2, columnspan=2, sticky="we", pady=2)
            e.bind("<KeyRelease>", lambda ev, k=chiave: self._scrive_formula(k))
            e.bind("<Return>", self.ridisegna)
            e.bind("<FocusOut>", self.ridisegna)
        self.v_aiuto_sigma = tk.StringVar(value="Formule in x, y e nelle colonne c0, c1, …")
        ttk.Label(f, textvariable=self.v_aiuto_sigma, foreground="#555", wraplength=380,
                  justify="left").grid(row=4, column=0, columnspan=4, sticky="w")
        g = ttk.Frame(f)
        g.grid(row=5, column=0, columnspan=4, sticky="w", pady=(2, 0))
        ttk.Button(g, text="Formule errori…", command=self.apri_gestore).pack(side="left")
        self.v_rel = tk.BooleanVar(value=False)
        ttk.Checkbutton(g, text="σ come pesi relativi (scala con √χ²rid)",
                        variable=self.v_rel, command=self.ridisegna).pack(side="left", padx=8)
        self.v_kev = tk.BooleanVar(value=True)
        self.ck_kev = ttk.Checkbutton(f, text="Asse x in energia (spettro calibrato)",
                                      variable=self.v_kev, command=self._cambia_unita,
                                      state="disabled")
        self.ck_kev.grid(row=6, column=0, columnspan=4, sticky="w", pady=(2, 0))
        g = ttk.Frame(f)
        g.grid(row=7, column=0, columnspan=4, sticky="w", pady=(4, 0))
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
                  foreground="#555").grid(row=8, column=0, columnspan=4, sticky="w")

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
        ttk.Label(f, text="Funzioni: exp log log10 sqrt sin cos tan erf erfc gamma sign "
                          "Heaviside abs; costante pi; potenze con ** o ^.",
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
        ttk.Button(g, text="Riapri da report…", command=self.riapri_da_report).pack(side="left")
        self.v_logx = tk.BooleanVar(value=False)
        ttk.Checkbutton(g, text="Scala log x", variable=self.v_logx,
                        command=self.ridisegna).pack(side="left", padx=(14, 0))
        self.v_log = tk.BooleanVar(value=False)
        ttk.Checkbutton(g, text="Scala log y", variable=self.v_log,
                        command=self.ridisegna).pack(side="left", padx=(10, 0))
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
        self._aggiorna_menu_sigma()
        self.v_aiuto_sigma.set("Nelle formule: " + d.variabili_formula())
        if d.spe:
            for k in ("x", "y"):
                self.cb[k].configure(state="disabled")
            self.v_x.set("canale / energia")
            self.v_y.set("conteggi")
            poisson = [n for n, (fm, _) in eng.ERRORI.items()
                       if fm.replace(" ", "") == eng.FORMULA_POISSON.replace(" ", "")]
            if poisson:
                self._imposta_sigma("sy", poisson[0])
            else:
                self._imposta_sigma("sy", FORMULA, eng.FORMULA_POISSON)
            self._imposta_sigma("sx", NESSUNA)
            self.ck_kev.configure(state="normal" if d.cal else "disabled")
            self.v_kev.set(bool(d.cal))
            lt = f", live time {d.lt:g} s" if d.lt is not None else ""
            self.stato(f"{d.nome}: {len(d.counts)} canali{lt}, "
                       + (f"calibrato in {d.unita}." if d.cal
                          else "non calibrato (asse in canali)."))
        else:
            et, info = d.etichette, d.info
            self.cb["x"]["values"] = et + [INDICE]
            self.cb["y"]["values"] = et
            for k in ("x", "y"):
                self.cb[k].configure(state="readonly")
            if len(et) == 1:
                self.v_x.set(INDICE)
                self.v_y.set(et[0])
                ix, iy = None, 0
            else:
                self.v_x.set(et[0])
                self.v_y.set(et[1])
                ix, iy = 0, 1
            nota = ""
            if d.nomi:
                # con l'intestazione: solo colonne con un nome da incertezza
                jy = trova_colonna_errore(d.nomi, iy)
                jx = trova_colonna_errore(d.nomi, ix) if ix is not None else None
                self._imposta_sigma("sy", et[jy] if jy is not None else NESSUNA)
                self._imposta_sigma("sx", et[jx] if jx is not None and jx != jy else NESSUNA)
                scelte = [f"σ y = {et[jy]}"] if jy is not None else []
                if jx is not None and jx != jy:
                    scelte.append(f"σ x = {et[jx]}")
                nota = (" Dall'intestazione: " + ", ".join(scelte) + "." if scelte
                        else " Nessuna σ riconosciuta dall'intestazione.")
            else:
                c2 = d.arr[:, 2] if len(et) >= 3 else np.array([])
                c2 = c2[np.isfinite(c2)]
                terza = c2.size > 0 and bool(np.all(c2 > 0))
                self._imposta_sigma("sy", et[2] if terza else NESSUNA)
                self._imposta_sigma("sx", NESSUNA)
                nota = (f" Ho preso {et[2]} come σ y: controlla che sia giusto." if terza
                        else " Nessuna σ y selezionata.")
            formato = eng.SEPARATORI[info["sep"]] + (", virgola decimale" if info["virgola"] else "")
            extra = ""
            if info["scartate"]:
                extra += f" Scartate {info['scartate']} righe con un numero di colonne diverso."
            if info["completate"]:
                extra += f" {info['completate']} righe incomplete (celle mancanti)."
            self.ck_kev.configure(state="disabled")
            self.stato(f"{d.nome}: {d.arr.shape[0]} righe, {d.arr.shape[1]} colonne "
                       f"(separatore: {formato}).{extra}{nota}")
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
        """Dati secondo le scelte correnti, con la maschera dell'intervallo e
        dei punti validi (valori mancanti o non finiti esclusi)."""
        if self.dati is None:
            return None
        x, y, sy, sx, xl, yl, err_sigma = self.dati.estrai(
            self.v_x.get(), self.v_y.get(), self.v_sel["sy"].get(), self.v_form["sy"].get(),
            self.v_sel["sx"].get(), self.v_form["sx"].get(), self.v_kev.get())
        valid = eng.punti_validi(x, y, sy, sx)
        lo, hi = num(self.v_lo.get()), num(self.v_hi.get())
        if lo is not None and hi is not None and lo > hi:
            lo, hi = hi, lo
        m = valid & eng.maschera_intervallo(x, lo, hi)
        firma = (self.dati.path, self.v_x.get(), self.v_y.get(),
                 self.v_sel["sy"].get(), self.v_form["sy"].get(),
                 self.v_sel["sx"].get(), self.v_form["sx"].get(),
                 self.v_kev.get(), self.v_rel.get(), lo, hi)
        return {"x": x, "y": y, "sy": sy, "sx": sx, "xl": xl, "yl": yl, "m": m,
                "valid": valid, "lo": lo, "hi": hi, "firma": firma, "err_sigma": err_sigma}

    # ------------------------------------------------------------ sigma
    def _valori_sigma(self):
        cols = self.dati.etichette if self.dati is not None and not self.dati.spe else []
        return [NESSUNA] + cols + list(eng.ERRORI) + [FORMULA]

    def _aggiorna_menu_sigma(self):
        valori = self._valori_sigma()
        for k in ("sy", "sx"):
            self.cb[k]["values"] = valori
            if self.v_sel[k].get() not in valori:
                self.v_sel[k].set(FORMULA if self.v_form[k].get().strip() else NESSUNA)

    def _imposta_sigma(self, chiave, scelta, formula=None):
        self.v_sel[chiave].set(scelta)
        if formula is not None:
            self.v_form[chiave].set(formula)
        elif scelta in eng.ERRORI:
            self.v_form[chiave].set(eng.ERRORI[scelta][0])
        elif scelta != FORMULA:
            self.v_form[chiave].set("")

    def _scelta_sigma(self, chiave):
        self._imposta_sigma(chiave, self.v_sel[chiave].get())
        self.ridisegna()

    def _scrive_formula(self, chiave):
        """Scrivendo nella casella si passa a "(formula)", a meno che il testo
        coincida con la formula del menu scelta."""
        sel, testo = self.v_sel[chiave].get(), self.v_form[chiave].get().strip()
        if sel in eng.ERRORI and testo == eng.ERRORI[sel][0]:
            return
        if sel != FORMULA and (testo or sel in eng.ERRORI):
            self.v_sel[chiave].set(FORMULA)

    def formula_proposta(self):
        """Formula da proporre aggiungendo una voce al menu degli errori."""
        for k in ("sy", "sx"):
            if self.v_sel[k].get() == FORMULA and self.v_form[k].get().strip():
                return self.v_form[k].get().strip()
        return ""

    def apri_gestore(self):
        if self.gestore is not None and self.gestore.winfo_exists():
            self.gestore.lift()
            return
        self.gestore = GestoreErrori(self)

    def _applica_errori(self, nuove, rinomina=None):
        """Salva il menu degli errori e aggiorna le scelte di σ y e σ x."""
        try:
            eng.salva_menu(nuove, eng.FILE_ERRORI, "formula")
        except OSError as e:
            self.errore("Non riesco a salvare le formule degli errori", e)
            return False
        eng.imposta_menu(eng.ERRORI, nuove)
        cols = self.dati.etichette if self.dati is not None and not self.dati.spe else []
        for k in ("sy", "sx"):
            sel = self.v_sel[k].get()
            if rinomina and sel == rinomina[0]:
                sel = rinomina[1]
                self.v_sel[k].set(sel)
            if sel in eng.ERRORI:
                self.v_form[k].set(eng.ERRORI[sel][0])       # formula modificata
            elif sel not in (NESSUNA, FORMULA) and sel not in cols:
                self.v_sel[k].set(FORMULA)                   # rimossa: resta la formula
        self._aggiorna_menu_sigma()
        self.ridisegna()
        return True

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
            eng.salva_menu(nuove, eng.FILE_LEGGI, "legge")
        except OSError as e:
            self.errore("Non riesco a salvare le leggi", e)
            return False
        eng.imposta_menu(eng.LEGGI, nuove)
        self.cb_pronta["values"] = [LIBERA] + list(eng.LEGGI)
        return True

    def _seleziona(self, nome):
        """Mostra nel menu la legge appena salvata, senza azzerare i valori dei
        parametri gia' scritti se la legge ha gli stessi parametri."""
        self.v_pronta.set(nome)
        self.v_legge.set(eng.LEGGI[nome][0])
        self.v_descr.set(eng.LEGGI[nome][1])
        self.leggi_parametri()

    def _dialogo_legge(self, titolo, **kw):
        return DialogoVoce(self.root, titolo, "Legge  y =", eng.LEGGI, controlla_legge,
                           nota="La descrizione è facoltativa. Variabile: x; tutti gli altri "
                                "nomi sono parametri.", **kw)

    def aggiungi_legge(self):
        d = self._dialogo_legge("Aggiungi legge al menu", testo=self.v_legge.get().strip())
        if d.risultato is None:
            return
        nome = d.risultato[0]
        if self._applica_leggi(eng.menu_con(eng.LEGGI, *d.risultato)):
            self._seleziona(nome)
            self.stato(f"Legge '{nome}' aggiunta al menu.")

    def modifica_legge(self):
        vecchio = self.v_pronta.get()
        if vecchio not in eng.LEGGI:
            self.stato("Scegli prima dal menu la legge da modificare.")
            return
        legge, descr = eng.LEGGI[vecchio]
        d = self._dialogo_legge(f"Modifica legge '{vecchio}'", nome=vecchio, testo=legge,
                                descr=descr, vecchio=vecchio)
        if d.risultato is None:
            return
        nome = d.risultato[0]
        if self._applica_leggi(eng.menu_con(eng.LEGGI, *d.risultato, vecchio)):
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
        if self._applica_leggi(dict(eng.PREDEFINITE_LEGGI)):
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
        if d["err_sigma"]:
            raise ValueError(d["err_sigma"])
        if d["m"].sum() < 2:
            raise ValueError("meno di due punti validi nell'intervallo scelto")
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
        except Exception as e:
            self.errore("Anteprima non riuscita", e)
            return
        self.ante = lambda xs: eng.valuta_curva(f, xs, p)
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
            legge, tab = self.v_legge.get().strip(), self.tabella()
            self.root.configure(cursor="watch")
            self.root.update_idletasks()
            try:
                ris = calcola_fit(legge, tab, d["x"][m], d["y"][m],
                                  sel(d["sy"]), sel(d["sx"]), self.v_der.get(),
                                  self.dati.nome + intervallo, self.v_rel.get())
                # impostazioni registrate adesso: il report salvato dopo deve
                # descrivere questo fit anche se nel frattempo si cambia la tabella
                nome = self.v_pronta.get()
                nome_legge = nome if nome in eng.LEGGI and eng.LEGGI[nome][0] == legge else None
                ris["impostazioni"] = eng.crea_impostazioni(
                    self._sorgente(d), legge, tab, self.v_der.get(), self.v_rel.get(), ris,
                    int(m.sum()), nome_legge)
            finally:
                self.root.configure(cursor="")
        except Exception as e:
            self.errore("Fit non riuscito", e)
            return False
        ris["firma"] = d["firma"]
        self.ris, self.ante = ris, None
        self.mostra_testo(ris["testo"])
        self.ridisegna()
        R = ris["R"]
        esclusi = int((~d["valid"]).sum())
        coda = f" Esclusi {esclusi} punti con valori mancanti." if esclusi else ""
        if R["note"]:
            coda += " Vedi le note nel report."
        if R["weighted"]:
            self.stato(f"Fit completato: χ² = {R['chi2']:.4g} con {R['ndof']} gradi di libertà "
                       f"(χ² ridotto {R['chi2r']:.3g}, p-value {R['pval']:.3g})." + coda)
        else:
            self.stato("Fit completato senza σ sui dati: incertezze stimate dai residui, "
                       "χ² non calcolabile." + coda)
        return True

    def _sorgente(self, d):
        """Scelte su file, colonne, sigma e intervallo, per le impostazioni del report."""
        dati = self.dati
        s = {"tipo": "spe" if dati.spe else "tabella", "file": dati.nome,
             "percorso": os.path.abspath(dati.path),
             "intervallo": [eng._jn(d["lo"]), eng._jn(d["hi"])]}
        if dati.spe:
            s["energia"] = bool(self.v_kev.get() and dati.cal)
        else:
            idx = lambda et: None if et == INDICE else dati.etichette.index(et)
            s["x"], s["y"] = idx(self.v_x.get()), idx(self.v_y.get())
        for chiave, k in (("sy", "sigma_y"), ("sx", "sigma_x")):
            sel = self.v_sel[chiave].get()
            if sel == NESSUNA:
                s[k] = {"tipo": "nessuna"}
            elif not dati.spe and sel in dati.etichette:
                s[k] = {"tipo": "colonna", "colonna": dati.etichette.index(sel)}
            else:   # si registra il testo della formula, non solo il nome nel menu
                s[k] = {"tipo": "formula", "formula": self.v_form[chiave].get().strip(),
                        "nome": sel if sel in eng.ERRORI else None}
        return s

    # ------------------------------------------------------------ riapri da report
    def riapri_da_report(self):
        path = filedialog.askopenfilename(title="Riapri fit da report",
                                          filetypes=[("Report", "*.txt"), ("Tutti i file", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                imp = eng.leggi_impostazioni(f.read())
        except (OSError, ValueError) as e:
            self.errore("Report non leggibile", e)
            return
        if imp.get("tipo") == "manuale":
            self.errore("Report non riapribile qui",
                        "i dati erano stati inseriti a mano nel terminale: rifai il fit con "
                        "python fit_legge.py --da-report " + os.path.basename(path))
            return
        dati_path = eng.trova_file_dati(imp, path)
        if dati_path is None:
            messagebox.showinfo("File dei dati",
                                f"Non trovo '{imp.get('file')}' né dove era stato aperto né nella "
                                "cartella del report: indicami dove si trova.")
            dati_path = filedialog.askopenfilename(title=f"Dov'è {imp.get('file')}?",
                                                   initialfile=imp.get("file") or "")
            if not dati_path:
                return
        self.apri(dati_path)
        if self.dati is None or self.dati.path != dati_path:
            return                                   # apertura non riuscita: errore gia' mostrato
        avvisi = []
        try:
            self._ripristina(imp, avvisi)
        except (ValueError, KeyError, TypeError, IndexError) as e:
            self.errore("Impostazioni non applicabili", e)
            return
        if not self.esegui_fit():
            return
        esito, righe = eng.confronta_risultati(imp, self.ris, int(self.ris["R"]["res"].size),
                                               dati_path)
        testo = "\n".join(righe + avvisi)
        self.stato(" ".join(righe + avvisi))
        (messagebox.showwarning if esito == "diverso" or avvisi else messagebox.showinfo)(
            "Riapri da report", testo)

    def _ripristina(self, imp, avvisi):
        """Applica alle caselle le impostazioni lette da un report."""
        d = self.dati
        completo = imp.get("completo", False)

        def etichetta(i):
            if i is None:
                return INDICE
            if not 0 <= int(i) < len(d.etichette):
                raise ValueError(f"il file non ha la colonna {i} (ha {len(d.etichette)} colonne)")
            return d.etichette[int(i)]

        if d.spe:
            if imp.get("tipo") == "tabella":
                avvisi.append("Il report era di un file a colonne, non di uno spettro.")
            if "energia" in imp:
                if imp["energia"] and not d.cal:
                    avvisi.append("Lo spettro non è più calibrato: uso i canali.")
                self.v_kev.set(bool(imp["energia"] and d.cal))
        elif "y" in imp:
            self.v_x.set(etichetta(imp.get("x")))
            self.v_y.set(etichetta(imp["y"]))
        for chiave, k in (("sy", "sigma_y"), ("sx", "sigma_x")):
            s = imp.get(k)
            if not s:
                continue                             # report vecchio: restano le scelte automatiche
            if s.get("tipo") == "colonna":
                if d.spe:
                    raise ValueError("il report usa una colonna come σ, ma il file è uno spettro")
                self._imposta_sigma(chiave, etichetta(s["colonna"]))
            elif s.get("tipo") == "formula":
                nome, formula = s.get("nome"), s.get("formula", "")
                if nome in eng.ERRORI and eng.ERRORI[nome][0] == formula:
                    self._imposta_sigma(chiave, nome)
                else:
                    self._imposta_sigma(chiave, FORMULA, formula)
                    if nome in eng.ERRORI:
                        avvisi.append(f"La formula '{nome}' del menu è cambiata dopo il fit: "
                                      "uso quella registrata nel report.")
            else:
                self._imposta_sigma(chiave, NESSUNA)
        self.v_rel.set(bool(imp.get("relativo", False)))
        lo, hi = (imp.get("intervallo") or [None, None])[:2]
        self.v_lo.set("" if lo is None else repr(float(lo)))
        self.v_hi.set("" if hi is None else repr(float(hi)))
        legge = imp["legge"]
        nome = imp.get("nome_legge")
        if nome in eng.LEGGI and eng.LEGGI[nome][0] == legge:
            self.v_pronta.set(nome)
            self.v_descr.set(eng.LEGGI[nome][1])
        else:
            self.v_pronta.set(LIBERA)
            self.v_descr.set("")
        self.v_legge.set(legge)
        self.righe = {}                              # tabella dei parametri nuova
        if self.leggi_parametri() is None:
            raise ValueError("la legge registrata nel report non è valida")
        testo = lambda v: "" if v is None else repr(float(v))
        for n, par in (imp.get("parametri") or {}).items():
            if n in self.righe:
                r = self.righe[n]
                r["val"].set(testo(par.get("iniziale")))
                r["lo"].set(testo(par.get("min")))
                r["hi"].set(testo(par.get("max")))
                r["fix"].set(bool(par.get("fisso")))
        self.v_der.set(imp.get("derivate", "") if completo else "")
        if not completo:
            avvisi.append("Report di una versione precedente: ho ripristinato legge, intervallo e "
                          "parametri (i risultati come valori iniziali). σ, colonne, limiti e "
                          "grandezze derivate non erano registrati: controllali.")
        self.ridisegna()

    # ------------------------------------------------------------ grafico
    def ridisegna(self, *_):
        ax, axr = self.ax, self.axr
        if self.span is not None:
            self.span.disconnect_events()
            self.span = None
        ax.clear()
        axr.clear()
        ax.set_xscale("linear")
        ax.set_yscale("linear")
        try:
            d = self.corrente()
        except ValueError as e:
            self.stato(f"Intervallo non valido: {e}")
            d = None
        if d is not None and not d["valid"].any():
            self.stato("Nessun punto valido con le colonne e le σ scelte.")
            d = None
        if d is None:
            ax.text(0.5, 0.5, "Apri un file di dati" if self.dati is None else "Nessun punto",
                    ha="center", va="center", transform=ax.transAxes, color="0.5")
            ax.set_xticks([]); ax.set_yticks([])
            axr.set_xticks([]); axr.set_yticks([])
            self.canvas.draw_idle()
            return
        x, y, sy, sx, m, valid = d["x"], d["y"], d["sy"], d["sx"], d["m"], d["valid"]
        if d["err_sigma"]:
            self.stato(d["err_sigma"])
        if self.ris and self.ris.get("firma") != d["firma"]:
            self.ris = None
            self.stato("Dati, σ o intervallo cambiati: riesegui il fit.")
        if not m.any():
            self.stato("Nessun punto nell'intervallo scelto.")

        # scala log x: solo con valori positivi; i calcoli dei limiti si fanno
        # nella scala mostrata (lineare o logaritmica)
        logx = self.v_logx.get() and bool(np.any(x[valid] > 0))
        if self.v_logx.get() and not logx:
            self.stato("Scala log x non applicabile: nessun valore di x positivo.")
        avanti, indietro = ((np.log10, lambda t: 10.0 ** t) if logx
                            else (lambda t: t, lambda t: t))
        ok_x = valid & (x > 0) if logx else valid
        mm = m & ok_x

        fuori = ok_x & ~m
        if fuori.any():
            ax.plot(x[fuori], y[fuori], ".", color="0.72", ms=3, label="fuori intervallo")
        if mm.any():
            if mm.sum() <= 600:
                ax.errorbar(x[mm], y[mm], yerr=None if sy is None else sy[mm],
                            xerr=None if sx is None else sx[mm], fmt="o", ms=3, lw=0.8,
                            color="C0", label="dati")
            else:
                ax.plot(x[mm], y[mm], ".", color="C0", ms=3, label="dati")
        esclusi = int((~valid).sum())
        if esclusi:
            ax.text(0.99, 0.01, f"{esclusi} punti esclusi (valori mancanti o non finiti)",
                    transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color="0.45")

        # limiti in x: tutto, oppure l'intervallo con un margine
        x0, x1 = float(avanti(x[ok_x].min())), float(avanti(x[ok_x].max()))
        if mm.any() and (d["lo"] is not None or d["hi"] is not None):
            a, b = float(avanti(x[mm].min())), float(avanti(x[mm].max()))
            w = (b - a) or 1.0
            v0, v1 = max(x0, a - 0.25 * w), min(x1, b + 0.25 * w)
        else:
            v0, v1 = x0, x1
        marg = 0.02 * ((v1 - v0) or 1.0)
        t0, t1 = v0 - marg, v1 + marg                 # nella scala mostrata
        v0, v1 = indietro(t0), indietro(t1)
        if mm.any():
            a, b = x[mm].min(), x[mm].max()
            xs = np.geomspace(a, b, 800) if logx and a > 0 else np.linspace(a, b, 800)
        else:
            xs = None
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
        vis = ok_x & (x >= v0) & (x <= v1)
        if vis.any():
            alto = y[vis] + (sy[vis] if sy is not None else 0)
            basso = y[vis] - (sy[vis] if sy is not None else 0)
            if self.v_log.get():
                pos = y[vis][y[vis] > 0]
                if len(pos):
                    ax.set_yscale("log")
                    ax.set_ylim(pos.min() * 0.6, max(alto.max(), pos.max()) * 1.8)
                else:
                    self.stato("Scala log y non applicabile: nessun valore positivo.")
            else:
                h = (alto.max() - basso.min()) or (abs(alto.max()) or 1.0)
                ax.set_ylim(basso.min() - 0.05 * h, alto.max() + 0.10 * h)
        if logx:
            ax.set_xscale("log")
        ax.set_xlim(v0, v1)
        ax.set_ylabel(d["yl"])
        axr.set_xlabel(d["xl"])
        ax.tick_params(labelbottom=False)

        # legenda a destra e riquadro a sinistra, in alto o in basso secondo
        # dove i dati lasciano spazio
        def dati_in_alto(lato):
            q = indietro(t0 + 0.3 * (t1 - t0)) if lato == "sin" else indietro(t1 - 0.3 * (t1 - t0))
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
        if ax.get_legend_handles_labels()[0]:
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
                if self.ris.get("impostazioni"):
                    fh.write(eng.blocco_impostazioni(self.ris["impostazioni"]))
            col = [d["x"][m], d["y"][m]]
            intest = ["x", "y"]
            for chiave, nome in (("sy", "sigma_y"), ("sx", "sigma_x")):
                if d[chiave] is not None:
                    col.append(d[chiave][m])
                    intest.append(nome)
            if d["sx"] is not None:
                col.append(R["s_eff"])
                intest.append("sigma_efficace")
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
