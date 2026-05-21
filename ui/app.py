import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
import json
from PIL import Image

from core.data_io import (
    build_export_payload, export_pdf_report,
    interpret_with_decision_tree, load_transport_data,
)
from core.solver import TransportationSolver
from ui.table_view import TableView
from ui.graph_view import (
    generate_cost_evolution_chart, generate_flow_distribution_chart,
    generate_network_flow_chart, save_figure_to_bytes,
)

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

ctk.set_appearance_mode("dark")

class App(ctk.CTk):
    BG      = "#1A0A0E"
    PANEL   = "#2D1218"
    CARD    = "#F7ECE4"
    SOFT    = "#FFF8F2"
    TXT_D   = "#33181B"
    TXT_L   = "#ffffff"
    TXT_M   = "#CFAE9E"
    GREY    = "#62545A"
    PINK    = "#B65B62"
    GOLD    = "#C9A15A"
    TEAL    = "#4AA6A0"

    def __init__(self):
        super().__init__()
        self.title("Logistica Vieții — Optimizarea Fluxurilor de Distribuție")
        self.configure(fg_color=self.BG)

        self.after(0, self._open_fullscreen)

        self.intrari_matrice_cost = []
        self.intrari_disponibil = []
        self.intrari_necesar = []
        self.final_state = None
        self.solution_states = []
        self.last_interpretation = None
        self.source_labels = []
        self.destination_labels = []
        self.import_metadata = {}
        self.logo_image = self._load_logo()
        self.logo_path = self._find_logo_path()

        self._build_ui()

    def _find_logo_path(self):
        m = list(Path(__file__).resolve().parents[1].glob("*.png"))
        return str(m[0]) if m else None

    def _open_fullscreen(self):
        try:
            self.state("zoomed")
        except tk.TclError:
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

    def _load_logo(self):
        m = list(Path(__file__).resolve().parents[1].glob("*.png"))
        if not m: return None
        try: return ctk.CTkImage(Image.open(m[0]), size=(220, 68))
        except: return None

    def _btn(self, parent, text, color, hover, cmd, **kw):
        return ctk.CTkButton(parent, text=text, font=("Cardo Bold", 13, "bold"),
            text_color=self.TXT_L, fg_color=color, hover_color=hover,
            corner_radius=8, height=40, command=cmd, **kw)

    def _build_ui(self):

        hdr = ctk.CTkFrame(self, fg_color=self.PANEL, corner_radius=0, height=80)
        hdr.pack(fill="x")
        hdr.grid_columnconfigure(0, weight=1)
        if self.logo_image:
            ctk.CTkLabel(hdr, image=self.logo_image, text="").grid(
                row=0, column=1, rowspan=2, padx=(10,20), pady=10, sticky="e")
        ctk.CTkLabel(hdr, text="Logistica Vieții", font=("Cardo Bold",26,"bold"),
                     text_color=self.TXT_L).grid(row=0, column=0, sticky="w", padx=(20,10), pady=(10,0))
        ctk.CTkLabel(hdr, text="Optimizarea fluxurilor vitale · Metoda transportului · Interpretare ML",
                     font=("TT Fors Trial Light",12), text_color=self.TXT_M
                     ).grid(row=1, column=0, sticky="w", padx=(20,10), pady=(0,10))

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=12, pady=(8,12))

        self.main_paned = tk.PanedWindow(
            main,
            orient="horizontal",
            bd=0,
            sashwidth=10,
            opaqueresize=True,
            bg=self.BG,
            sashrelief="flat",
            showhandle=False,
        )
        self.main_paned.pack(fill="both", expand=True)

        left = ctk.CTkFrame(self.main_paned, fg_color=self.PANEL, corner_radius=10, width=320)
        left.pack_propagate(False)

        sec1 = ctk.CTkFrame(left, fg_color=self.CARD, corner_radius=8)
        sec1.pack(fill="x", padx=10, pady=(12,6))
        ctk.CTkLabel(sec1, text="Configurare rețea", font=("Cardo Bold",14,"bold"),
                     text_color=self.TXT_D).pack(pady=(8,4))

        row_mn = ctk.CTkFrame(sec1, fg_color="transparent")
        row_mn.pack(pady=4)
        ctk.CTkLabel(row_mn, text="m", font=("TT Fors Trial Light",12,"bold"),
                     text_color=self.TXT_D).pack(side="left", padx=(8,2))
        self.entry_m = ctk.CTkEntry(row_mn, width=42, height=26, font=("TT Fors Trial Light",12,"bold"),
            fg_color="#fff", text_color=self.TXT_D, border_color=self.PINK, justify="center")
        self.entry_m.pack(side="left", padx=(0,10))
        ctk.CTkLabel(row_mn, text="n", font=("TT Fors Trial Light",12,"bold"),
                     text_color=self.TXT_D).pack(side="left", padx=(0,2))
        self.entry_n = ctk.CTkEntry(row_mn, width=42, height=26, font=("TT Fors Trial Light",12,"bold"),
            fg_color="#fff", text_color=self.TXT_D, border_color=self.PINK, justify="center")
        self.entry_n.pack(side="left")

        self._btn(sec1, "Generează rețeaua", self.GREY, "#4C4146",
                  self.generate_input_grid).pack(fill="x", padx=12, pady=(4,8))

        self._btn(left, "Importă date", self.TEAL, "#377F7B",
                  self.import_data).pack(fill="x", padx=10, pady=(8,4))

        self.frame_input = ctk.CTkScrollableFrame(left, fg_color=self.CARD, corner_radius=8,
            scrollbar_button_color=self.PANEL, scrollbar_button_hover_color="#5A232A")
        self.frame_input.pack(fill="both", expand=True, padx=10, pady=6)

        self.left_actions = ctk.CTkFrame(left, fg_color="transparent")
        self.left_actions.pack(fill="x", padx=10, pady=(4,10))

        self.btn_solve = self._btn(self.left_actions, "Simulează fluxurile",
                                   self.BG, "#4A1D24", self.solve_problem)

        self.btn_interp = self._btn(self.left_actions, "Interpretare ML",
                                    self.GOLD, "#A98543", self.arata_interpretarea)
        self.btn_chart = self._btn(self.left_actions, "Grafice analitice",
                                   self.PINK, "#9A4A50", self.arata_grafice)
        self.btn_export = self._btn(self.left_actions, "Export (JSON + PDF)",
                                    self.TEAL, "#377F7B", self.export_data)

        right = ctk.CTkFrame(self.main_paned, fg_color="transparent", width=980)

        self.status_bar = ctk.CTkFrame(right, fg_color=self.PANEL, corner_radius=8, height=36)
        self.status_bar.pack(fill="x", pady=(0,6))
        self.status_label = ctk.CTkLabel(self.status_bar,
            text="  Importați date sau generați o rețea pentru a începe",
            font=("TT Fors Trial Light",12), text_color=self.TXT_M, anchor="w")
        self.status_label.pack(fill="x", padx=12, pady=6)

        self.frame_results = ctk.CTkScrollableFrame(right, fg_color="transparent",
            corner_radius=10, scrollbar_button_color="#5A232A",
            scrollbar_button_hover_color="#6E2C34")
        self.frame_results.pack(fill="both", expand=True)

        self.main_paned.add(left, minsize=290, padx=0, pady=0)
        self.main_paned.add(right, minsize=760, padx=0, pady=0)
        self.after(0, self._set_initial_sash)

    def _set_initial_sash(self):
        try:
            total_width = self.main_paned.winfo_width()
            left_width = max(300, min(360, int(total_width * 0.27)))
            self.main_paned.sash_place(0, left_width, 0)
        except tk.TclError:
            pass

    def _auto_fit_layout_for_matrix(self, m, n):
        self.update_idletasks()

        max_src = max((len(str(label)) for label in (self.source_labels or [f"A{i+1}" for i in range(m)])), default=2)
        max_dst = max((len(str(label)) for label in (self.destination_labels or [f"B{j+1}" for j in range(n)])), default=2)

        label_col = max(44, min(96, 22 + max_src * 5))
        data_col = max(34, min(60, 20 + max_dst * 4))
        supply_col = 48
        grid_width = label_col + supply_col + n * (data_col + 2) + 20
        left_width = max(285, min(430, grid_width + 34))

        try:
            total_width = self.main_paned.winfo_width()
            max_left = max(285, total_width - 560)
            self.main_paned.sash_place(0, min(left_width, max_left), 0)
        except tk.TclError:
            pass

    def _clear_results(self):
        for w in self.frame_results.winfo_children(): w.destroy()
        self.btn_interp.pack_forget()
        self.btn_chart.pack_forget()
        self.btn_export.pack_forget()
        self.final_state = None
        self.solution_states = []
        self.last_interpretation = None
        self.status_label.configure(text="  Importați date sau generați o rețea pentru a începe")

    def _clear_input_grid(self):
        for w in self.frame_input.winfo_children(): w.destroy()
        self.intrari_matrice_cost.clear()
        self.intrari_disponibil.clear()
        self.intrari_necesar.clear()
        self.btn_solve.pack_forget()

    def generate_input_grid(self):
        self._clear_results(); self._clear_input_grid()
        try:
            m = int(self.entry_m.get()); n = int(self.entry_n.get())
            if m <= 0 or n <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Eroare", "Introduceți numere întregi pozitive!"); return
        self.source_labels = [f"A{i+1}" for i in range(m)]
        self.destination_labels = [f"B{j+1}" for j in range(n)]
        self.import_metadata = {}
        self._build_input_grid(m, n)

    def _build_input_grid(self, m, n, imported=None):
        grid_f = ctk.CTkFrame(self.frame_input, fg_color="transparent")
        grid_f.pack(pady=(8,4))
        fl = ("TT Fors Trial Light", 10, "bold")
        fe = ("TT Fors Trial Light", 10, "bold")

        for j in range(n):
            lb = self.destination_labels[j] if j < len(self.destination_labels) else f"B{j+1}"
            ctk.CTkLabel(grid_f, text=lb, font=fl, text_color=self.TXT_D).grid(row=0, column=j+1, padx=2, pady=1)
        ctk.CTkLabel(grid_f, text="Disp.", font=fl, text_color=self.BG).grid(row=0, column=n+1, padx=4)

        for i in range(m):
            lb = self.source_labels[i] if i < len(self.source_labels) else f"A{i+1}"
            ctk.CTkLabel(grid_f, text=lb, font=fl, text_color=self.TXT_D).grid(row=i+1, column=0, padx=4)
            row_entries = []
            for j in range(n):
                e = ctk.CTkEntry(grid_f, width=34, height=20, font=fe, justify="center",
                    fg_color="#fff", text_color=self.TXT_D, border_color=self.PINK)
                e.grid(row=i+1, column=j+1, padx=1, pady=1)
                if imported: e.insert(0, f"{imported.cost[i][j]:g}")
                row_entries.append(e)
            self.intrari_matrice_cost.append(row_entries)
            es = ctk.CTkEntry(grid_f, width=40, height=20, font=fe, justify="center",
                fg_color="#fff", text_color=self.TXT_D, border_color=self.BG)
            es.grid(row=i+1, column=n+1, padx=4)
            if imported: es.insert(0, f"{imported.supply[i]:g}")
            self.intrari_disponibil.append(es)

        ctk.CTkLabel(grid_f, text="Nec.", font=fl, text_color=self.BG).grid(row=m+1, column=0, padx=4, pady=(3,1))
        for j in range(n):
            ed = ctk.CTkEntry(grid_f, width=34, height=20, font=fe, justify="center",
                fg_color="#fff", text_color=self.TXT_D, border_color=self.BG)
            ed.grid(row=m+1, column=j+1, padx=1, pady=(3,1))
            if imported: ed.insert(0, f"{imported.demand[j]:g}")
            self.intrari_necesar.append(ed)

        if imported and (imported.title or imported.scenario or imported.notes):
            meta = " | ".join(p for p in [imported.title, imported.scenario, imported.notes] if p)
            ctk.CTkLabel(self.frame_input, text=meta, font=("TT Fors Trial Light",10),
                         text_color=self.GREY, wraplength=230).pack(pady=(0,4))

        self.btn_solve.pack(fill="x", pady=(6,0))
        self.after(0, lambda: self._auto_fit_layout_for_matrix(m, n))
        self.status_label.configure(text="  Rețea generată. Completați datele și simulați.")

    def import_data(self):
        fp = filedialog.askopenfilename(title="Importă date",
            filetypes=[("Date transport","*.json *.csv *.txt"),("Toate","*.*")])
        if not fp: return
        try: imported = load_transport_data(fp)
        except Exception as e: messagebox.showerror("Import nereușit", str(e)); return

        self._clear_results(); self._clear_input_grid()
        m, n = len(imported.supply), len(imported.demand)
        self.entry_m.delete(0,"end"); self.entry_m.insert(0, str(m))
        self.entry_n.delete(0,"end"); self.entry_n.insert(0, str(n))
        self.source_labels = imported.source_labels
        self.destination_labels = imported.destination_labels
        self.import_metadata = {"fisier_import": str(fp), "titlu": imported.title,
                                "scenariu": imported.scenario, "note": imported.notes}
        self._build_input_grid(m, n, imported=imported)
        messagebox.showinfo("Import finalizat", "Datele au fost încărcate.")

    def solve_problem(self):
        self._clear_results()
        try:
            m = len(self.intrari_disponibil); n = len(self.intrari_necesar)
            cost = [[float(self.intrari_matrice_cost[i][j].get().replace(",","."))
                      for j in range(n)] for i in range(m)]
            disp = [float(e.get().replace(",",".")) for e in self.intrari_disponibil]
            nec = [float(e.get().replace(",",".")) for e in self.intrari_necesar]
        except ValueError:
            messagebox.showerror("Eroare", "Date invalide!"); return

        solver = TransportationSolver(cost, disp, nec)
        for state in solver.solve():
            state["source_labels"] = self.source_labels
            state["destination_labels"] = self.destination_labels
            self.solution_states.append(state)

            it = state['iteratie']
            title = f"Iterația {it} (N-V)" if it == 0 else f"Iterația {it}"

            card = ctk.CTkFrame(self.frame_results, fg_color=self.CARD, corner_radius=8)
            card.pack(pady=6, fill="x", padx=4)
            TableView(card, state, title=title, fg_color="transparent").pack(pady=10, padx=10, fill="x")

            if state['este_optim']:
                self.final_state = state

        if self.final_state:
            n_it = len(self.solution_states) - 1
            c = self.solution_states[-1].get('mesaj_explicativ','').split(":")[-1].strip() if self.solution_states else ""
            self.status_label.configure(
                text=f"  Soluție optimă - {n_it} iterații - Cost optim: {c}")
            self.btn_interp.pack(fill="x", pady=(6,3))
            self.btn_chart.pack(fill="x", pady=3)
            self.btn_export.pack(fill="x", pady=(3,0))

    def _current_input_payload(self):
        cost = [[float(e.get().replace(",",".")) for e in row] for row in self.intrari_matrice_cost]
        return {
            "surse": self.source_labels or [f"A{i+1}" for i in range(len(self.intrari_disponibil))],
            "destinatii": self.destination_labels or [f"B{j+1}" for j in range(len(self.intrari_necesar))],
            "matrice_costuri": cost,
            "disponibil": [float(e.get().replace(",",".")) for e in self.intrari_disponibil],
            "necesar": [float(e.get().replace(",",".")) for e in self.intrari_necesar],
        }

    def _build_interpretation(self):
        if not self.solution_states: return None
        p = self._current_input_payload()
        self.last_interpretation = interpret_with_decision_tree(
            p["matrice_costuri"], p["disponibil"], p["necesar"],
            self.solution_states, p["surse"], p["destinatii"])
        return self.last_interpretation

    def arata_interpretarea(self):
        if not self.final_state: return
        interp = self._build_interpretation()
        if not interp: return

        pop = ctk.CTkToplevel(self)
        pop.title("Interpretare ML"); pop.geometry("760x640")
        pop.configure(fg_color=self.BG); pop.attributes("-topmost", True)

        card = ctk.CTkFrame(pop, fg_color=self.CARD, corner_radius=8)
        card.pack(pady=16, padx=16, fill="both", expand=True)

        ctk.CTkLabel(card, text="Interpretare ușoară a rezultatului",
            font=("Cardo Bold",22,"bold"), text_color=self.TXT_D).pack(pady=(14,2))
        ctk.CTkLabel(card,
            text=f"{interp['model_ales']} | Verdict: {interp['verdict']} | Risc: {interp['scor_risc']}/100",
            font=("TT Fors Trial Light",14,"bold"), text_color=self.PINK).pack(pady=(0,10))

        sf = ctk.CTkScrollableFrame(card, fg_color=self.SOFT, corner_radius=8)
        sf.pack(pady=(0,14), padx=14, fill="both", expand=True)

        def sec(title, lines):
            ctk.CTkLabel(sf, text=title, font=("Cardo Bold",16,"bold"),
                         text_color=self.TXT_D).pack(anchor="w", padx=10, pady=(12,3))
            for l in lines:
                ctk.CTkLabel(sf, text=l, font=("TT Fors Trial Light",13),
                    text_color=self.TXT_D, justify="left", anchor="w",
                    wraplength=660).pack(anchor="w", padx=18, pady=1)

        eff, eq, tm = interp["eficienta"], interp["echilibru"], interp["tumora"]
        user_summary = interp.get("rezumat_utilizator", {})
        if user_summary:
            sec("Pe înțelesul tuturor", [user_summary.get("titlu", ""), user_summary.get("mesaj", "")])
            sec("Ce s-a întâmplat", user_summary.get("puncte", []))
        sec("Explicație tehnică", [interp["regula_decizie"], f"Nivel risc: {interp.get('nivel_risc', '-')}"])
        sec("Eficiența sistemului", [
            f"Ofertă: {eq['oferta_totala']:g} | Cerere: {eq['cerere_totala']:g} | Echilibrat: {'da' if eq['sistem_echilibrat'] else 'nu'}",
            f"Cost inițial: {eff['cost_initial']:g} → Optim: {eff['cost_optim']:g} UM | Economie: {eff['economie_efort_procente']:g}%"])
        sec("Punct de consum parazit", [
            f"Detectat: {'da' if tm['detectata'] else 'nu'} | Dest: {tm['destinatie'] or '-'}",
            f"Flux: {tm['flux_primit']:g} | Pondere: {tm['pondere_flux']:g}% | Angiogenic: {'da' if tm['avantaj_angiogenic'] else 'nu'}"])
        sec("Acoperire destinații", [
            f"{i['destinatie']}: {i['acoperit']:g}/{i['necesar']:g} ({i['acoperire_procente']:.0f}%)"
            for i in interp["acoperire_destinatii"]])
        sec("Strategii", interp["recomandari"])

    def arata_grafice(self):
        if not self.solution_states or not self.final_state:
            messagebox.showwarning("Grafice", "Rulați simularea mai întâi."); return
        p = self._current_input_payload()

        pop = ctk.CTkToplevel(self)
        pop.title("Grafice Analitice"); pop.geometry("920x680")
        pop.configure(fg_color=self.BG); pop.attributes("-topmost", True)

        tv = ctk.CTkTabview(pop, fg_color=self.PANEL,
            segmented_button_fg_color=self.GREY,
            segmented_button_selected_color=self.PINK,
            segmented_button_selected_hover_color="#9A4A50",
            segmented_button_unselected_color=self.GREY,
            segmented_button_unselected_hover_color="#4C4146")
        tv.pack(fill="both", expand=True, padx=14, pady=14)

        for name, gen in [
            ("Evoluție Cost", lambda: generate_cost_evolution_chart(self.solution_states, dpi=100)),
            ("Distribuție Fluxuri", lambda: generate_flow_distribution_chart(
                self.final_state, p["destinatii"], p["necesar"], dpi=100)),
            ("Hartă Fluxuri", lambda: generate_network_flow_chart(
                self.final_state, p["surse"], p["destinatii"], dpi=100)),
        ]:
            tab = tv.add(name)
            fig = gen()
            c = FigureCanvasTkAgg(fig, master=tab)
            c.draw(); c.get_tk_widget().pack(fill="both", expand=True)

    def export_data(self):
        if not self.solution_states:
            messagebox.showwarning("Export", "Rulați simularea mai întâi."); return
        if self.last_interpretation is None: self._build_interpretation()

        fp = filedialog.asksaveasfilename(title="Exportă raportul (JSON + PDF)",
            defaultextension=".json", initialfile="raport_logistica_vietii.json",
            filetypes=[("JSON","*.json"),("Toate","*.*")])
        if not fp: return

        inp = self._current_input_payload()
        payload = build_export_payload(inp, self.solution_states,
                                       self.last_interpretation, self.import_metadata)

        jp = Path(fp)
        try: jp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as e: messagebox.showerror("Export JSON", str(e)); return

        cb = []
        try:
            cb.append(save_figure_to_bytes(generate_cost_evolution_chart(self.solution_states)))
            cb.append(save_figure_to_bytes(generate_flow_distribution_chart(
                self.final_state, inp["destinatii"], inp["necesar"])))
            cb.append(save_figure_to_bytes(generate_network_flow_chart(
                self.final_state, inp["surse"], inp["destinatii"])))
        except: pass

        pp = jp.with_suffix(".pdf")
        try:
            export_pdf_report(payload, str(pp), logo_path=self.logo_path,
                              chart_images=cb if cb else None)
        except Exception as e:
            messagebox.showerror("Export PDF", str(e))
            messagebox.showinfo("Export parțial", f"JSON salvat:\n{jp}"); return

        messagebox.showinfo("Export finalizat",
            f"Salvat cu succes:\n\nJSON: {jp.name}\nPDF: {pp.name}\n\nÎn: {jp.parent}")
