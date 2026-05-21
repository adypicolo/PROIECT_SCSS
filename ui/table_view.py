import tkinter as tk
import customtkinter as ctk

class TableView(ctk.CTkFrame):
    def __init__(self, master, stare, title="Iterație", **kwargs):
        super().__init__(master, **kwargs)

        self.stare = stare
        self.m = stare['m']
        self.n = stare['n']

        self.cost = stare['cost']
        self.alocari = stare['alocari']
        self.u = stare['u']
        self.v = stare['v']
        self.delta = stare['delta']
        self.circuit = stare['circuit']
        self.pivot = stare['pivot']
        self.disp = stare['disp']
        self.nec = stare['nec']
        self.source_labels = stare.get('source_labels') or [f"A{i + 1}" for i in range(self.m)]
        self.destination_labels = stare.get('destination_labels') or [f"B{j + 1}" for j in range(self.n)]

        self.color_bg = "#FFF8F2"
        self.color_cell = "#ffffff"
        self.color_header = "#B65B62"
        self.color_sum_bg = "#1A0A0E"

        self.color_text_dark = "#33181B"
        self.color_text_light = "#ffffff"

        self.color_pivot = "#62545A"
        self.color_cycle = "#C9A15A"
        self.color_negative = "#B65B62"
        self.color_success = "#2E8B57"

        icon = "OK" if stare['este_optim'] else ""
        icon_color = self.color_success if stare['este_optim'] else self.color_cycle

        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(pady=(0, 6))

        ctk.CTkLabel(title_frame, text=icon, font=("TT Fors Trial Light", 20, "bold"),
                     text_color=icon_color).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(title_frame, text=title, font=("Cardo Bold", 18, "bold"),
                     text_color=self.color_text_dark).pack(side="left")

        explicatie = stare.get('mesaj_explicativ', '')
        if explicatie:
            textbox = ctk.CTkTextbox(
                self,
                fg_color="#ffffff",
                text_color=self.color_text_dark,
                font=("TT Fors Trial Light", 14),
                wrap="word",
                height=110,
                corner_radius=8,
                border_color="#D48383",
                border_width=1,
                scrollbar_button_hover_color="#fff9ed",
                scrollbar_button_color="#fff9ed"
            )
            textbox.pack(pady=5, padx=10, fill="x")
            textbox.insert("0.0", explicatie)
            textbox.configure(state="disabled")

        if stare['este_optim']:
            opt_frame = ctk.CTkFrame(self, fg_color="#E8F5E9", corner_radius=8)
            opt_frame.pack(pady=8, padx=10, fill="x")
            ctk.CTkLabel(opt_frame, text="SOLUȚIE OPTIMĂ ATINSĂ",
                         font=("Cardo Bold", 20, "bold"),
                         text_color=self.color_success).pack(pady=10)

        max_label = max([len(str(x)) for x in self.source_labels + self.destination_labels] + [3])
        self.cell_w = max(92, min(128, 72 + max_label * 4))
        self.cell_h = 65
        self.corner_r = 6

        canvas_width = (self.n + 2) * self.cell_w
        canvas_height = (self.m + 2) * self.cell_h

        canvas_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        canvas_wrapper.pack(pady=15)

        self.canvas = tk.Canvas(canvas_wrapper, width=canvas_width, height=canvas_height,
                                bg=self.color_bg, highlightthickness=0)
        self.canvas.pack()

        self._draw_table()

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs):

        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _draw_table(self):
        cw = self.cell_w
        ch = self.cell_h
        cr = self.corner_r

        font_math = ("TT Fors Trial Light", 12, "bold")
        font_cost = ("TT Fors Trial Light", 11, "bold")
        font_main = ("TT Fors Trial Light", 13, "bold")
        font_small = ("TT Fors Trial Light", 10, "bold")

        pad = 2

        def draw_cell(x, y, w, h, bg_col, text, t_font, t_col, anchor="center", text_x_offset=0, text_y_offset=0):
            self._rounded_rect(x + pad, y + pad, x + w - pad, y + h - pad, cr, fill=bg_col, outline="")
            tx = x + w / 2 if anchor == "center" else x + text_x_offset
            ty = y + h / 2 if anchor == "center" else y + text_y_offset
            self.canvas.create_text(tx, ty, text=text, font=t_font, fill=t_col, anchor=anchor)

        def compact_label(label, fallback):
            value = str(label or fallback)
            return value if len(value) <= 12 else value[:11] + "."

        draw_cell(0, 0, cw, ch, self.color_header, "u / v", font_math, self.color_text_light)

        for j in range(self.n):
            v_val = f"{self.v[j]:g}" if self.v[j] is not None else "-"
            label = compact_label(self.destination_labels[j] if j < len(self.destination_labels) else f"B{j + 1}", f"B{j + 1}")
            draw_cell((j + 1) * cw, 0, cw, ch, self.color_header, f"{label}\nv={v_val}", font_small, self.color_text_light)

        for i in range(self.m):
            u_val = f"{self.u[i]:g}" if self.u[i] is not None else "-"
            label = compact_label(self.source_labels[i] if i < len(self.source_labels) else f"A{i + 1}", f"A{i + 1}")
            draw_cell(0, (i + 1) * ch, cw, ch, self.color_header, f"{label}\nu={u_val}", font_small, self.color_text_light)

        x_sum = (self.n + 1) * cw
        y_sum = (self.m + 1) * ch
        draw_cell(x_sum, 0, cw, ch, self.color_sum_bg, "Σ (D)", font_math, self.color_text_light)
        draw_cell(0, y_sum, cw, ch, self.color_sum_bg, "ΣC (N)", font_math, self.color_text_light)

        for i in range(self.m):

            draw_cell(x_sum, (i + 1) * ch, cw, ch, self.color_sum_bg, str(self.disp[i]), font_math,
                      self.color_text_light)
        for j in range(self.n):
            draw_cell((j + 1) * cw, y_sum, cw, ch, self.color_sum_bg, str(self.nec[j]), font_math,
                      self.color_text_light)

        total_sum = sum(self.disp, start=type(self.disp[0])(0))
        draw_cell(x_sum, y_sum, cw, ch, self.color_success, str(total_sum), font_math, "#FFFFFF")

        for i in range(self.m):
            for j in range(self.n):
                x = (j + 1) * cw
                y = (i + 1) * ch

                fill_color = self.color_cell
                text_color = self.color_text_dark

                if self.pivot == (i, j):
                    fill_color = self.color_pivot
                    text_color = "#FFFFFF"
                elif self.circuit and (i, j) in self.circuit:
                    fill_color = self.color_cycle
                    text_color = self.color_text_dark

                self._rounded_rect(x + pad, y + pad, x + cw - pad, y + ch - pad, cr, fill=fill_color, outline="")

                if self.circuit and (i, j) in self.circuit and self.pivot != (i, j):
                    self.canvas.create_rectangle(
                        x + pad + 1, y + pad + 1, x + cw - pad - 1, y + ch - pad - 1,
                        outline=self.color_cycle, width=2, dash=(4, 3)
                    )

                c_col = "#9C3032" if fill_color in {self.color_cell, self.color_cycle} else "#ffffff"
                self.canvas.create_text(x + 8, y + 8, text=f"{self.cost[i][j]:g}", font=font_cost, fill=c_col,
                                        anchor="nw")

                if (i, j) in self.alocari:
                    val_str = str(self.alocari[(i, j)])
                    if self.circuit and (i, j) in self.circuit:
                        idx = self.circuit.index((i, j))
                        sign = "(+)" if idx % 2 == 0 else "(-)"
                        val_str += f" {sign}"
                    self.canvas.create_text(x + cw / 2, y + ch / 2, text=val_str, font=font_main, fill=text_color)
                else:
                    d_val = self.delta.get((i, j), 0)
                    if d_val < 0:
                        self.canvas.create_text(x + cw / 2, y + ch / 2, text=f"({d_val:g})", font=font_math,
                                                fill=self.color_negative)
