import csv
import json
import statistics
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from reportlab.lib import colors as rl_colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

@dataclass
class ImportedTransportData:
    cost: list[list[float]]
    supply: list[float]
    demand: list[float]
    source_labels: list[str]
    destination_labels: list[str]
    title: str = ""
    scenario: str = ""
    notes: str = ""

def _as_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = str(value).strip().replace(" ", "")
    if not cleaned:
        raise ValueError("valoare numerica lipsa")
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)

def _first_present(data: dict[str, Any], *keys: str, default=None):
    normalized = {str(k).lower(): v for k, v in data.items()}
    for key in keys:
        if key.lower() in normalized:
            return normalized[key.lower()]
    return default

def _normalize_import(data: dict[str, Any]) -> ImportedTransportData:
    cost = _first_present(data, "cost", "costuri", "matrice_costuri", "matrice", "cost_matrix")
    supply = _first_present(data, "disponibil", "oferta", "supply", "capacitate", "capacitate_surse")
    demand = _first_present(data, "necesar", "cerere", "demand", "necesar_destinatii")

    if cost is None or supply is None or demand is None:
        raise ValueError("Fisierul trebuie sa contina cost/matrice_costuri, disponibil/oferta si necesar/cerere.")

    cost_matrix = [[_as_float(cell) for cell in row] for row in cost]
    supply_values = [_as_float(value) for value in supply]
    demand_values = [_as_float(value) for value in demand]

    if len(cost_matrix) != len(supply_values):
        raise ValueError("Numarul de randuri din matricea de costuri nu coincide cu numarul surselor.")
    if any(len(row) != len(demand_values) for row in cost_matrix):
        raise ValueError("Numarul de coloane din matricea de costuri nu coincide cu numarul destinatiilor.")

    sources = _first_present(data, "surse", "sources", "source_labels", default=None)
    destinations = _first_present(data, "destinatii", "destinatii_organe", "destinations", "destination_labels", default=None)

    source_labels = [str(x) for x in sources] if sources else [f"A{i + 1}" for i in range(len(supply_values))]
    destination_labels = [str(x) for x in destinations] if destinations else [f"B{j + 1}" for j in range(len(demand_values))]

    if len(source_labels) != len(supply_values):
        source_labels = [f"A{i + 1}" for i in range(len(supply_values))]
    if len(destination_labels) != len(demand_values):
        destination_labels = [f"B{j + 1}" for j in range(len(demand_values))]

    return ImportedTransportData(
        cost=cost_matrix,
        supply=supply_values,
        demand=demand_values,
        source_labels=source_labels,
        destination_labels=destination_labels,
        title=str(_first_present(data, "titlu", "title", default="")),
        scenario=str(_first_present(data, "scenariu", "scenario", default="")),
        notes=str(_first_present(data, "note", "notes", "descriere", "description", default="")),
    )

def _read_csv(path: Path) -> ImportedTransportData:
    raw = path.read_text(encoding="utf-8-sig")
    sample = raw[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    rows = [
        [cell.strip() for cell in row]
        for row in csv.reader(raw.splitlines(), dialect)
        if any(cell.strip() for cell in row)
    ]
    if len(rows) < 2:
        raise ValueError("Fisierul CSV nu contine suficiente randuri.")

    metadata = {}
    table_start = 0
    for idx, row in enumerate(rows):
        key = row[0].strip().lower()
        if len(row) == 2 and key in {"titlu", "title", "scenariu", "scenario", "note", "notes", "descriere"}:
            metadata[key] = row[1]
            table_start = idx + 1
            continue
        table_start = idx
        break

    table = rows[table_start:]
    if not table:
        raise ValueError("Fisierul CSV nu contine tabelul de transport.")

    header = table[0]
    supply_col = len(header) - 1
    destination_labels = header[1:supply_col]

    cost_rows = []
    source_labels = []
    demand_values = None

    for row in table[1:]:
        label = row[0].strip()
        label_lower = label.lower()
        if label_lower in {"n", "necesar", "cerere", "demand", "d"}:
            demand_values = [_as_float(cell) for cell in row[1:1 + len(destination_labels)]]
            break

        source_labels.append(label or f"A{len(source_labels) + 1}")
        costs = [_as_float(cell) for cell in row[1:1 + len(destination_labels)]]
        supply = _as_float(row[supply_col])
        cost_rows.append((costs, supply))

    if demand_values is None:
        last_row = table[-1]
        demand_values = [_as_float(cell) for cell in last_row[1:1 + len(destination_labels)]]
        data_rows = table[1:-1]
        cost_rows = []
        source_labels = []
        for row in data_rows:
            source_labels.append(row[0].strip() or f"A{len(source_labels) + 1}")
            cost_rows.append((
                [_as_float(cell) for cell in row[1:1 + len(destination_labels)]],
                _as_float(row[supply_col]),
            ))

    return ImportedTransportData(
        cost=[row[0] for row in cost_rows],
        supply=[row[1] for row in cost_rows],
        demand=demand_values,
        source_labels=source_labels,
        destination_labels=destination_labels,
        title=metadata.get("titlu", metadata.get("title", "")),
        scenario=metadata.get("scenariu", metadata.get("scenario", "")),
        notes=metadata.get("note", metadata.get("notes", metadata.get("descriere", ""))),
    )

def load_transport_data(file_path: str) -> ImportedTransportData:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".json":
        return _normalize_import(json.loads(path.read_text(encoding="utf-8-sig")))
    if suffix in {".csv", ".txt"}:
        return _read_csv(path)
    raise ValueError("Format neacceptat. Folositi JSON, CSV sau TXT.")

def _epsilon_payload(value: Any) -> dict[str, Any]:
    return {
        "valoare": str(value),
        "real": getattr(value, "real", None),
        "epsilon": getattr(value, "eps", None),
    }

def compute_transport_cost(state: dict[str, Any]) -> float:
    cost_total = 0.0
    orig_m = state["original_m"]
    orig_n = state["original_n"]

    for (i, j), quantity in state["alocari"].items():
        if i < orig_m and j < orig_n:
            cost_total += quantity.real * state["cost"][i][j]
    return cost_total

def build_export_payload(
    input_payload: dict[str, Any],
    states: list[dict[str, Any]],
    interpretation: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    exported_states = []
    for state in states:
        exported_states.append({
            "iteratie": state["iteratie"],
            "este_optim": state["este_optim"],
            "cost_transport_real": compute_transport_cost(state),
            "pivot": state["pivot"],
            "circuit": state["circuit"],
            "u": state["u"],
            "v": state["v"],
            "delta": {f"A{i + 1}->B{j + 1}": value for (i, j), value in state["delta"].items()},
            "alocari": {
                f"A{i + 1}->B{j + 1}": _epsilon_payload(value)
                for (i, j), value in state["alocari"].items()
            },
            "mesaj_explicativ": state.get("mesaj_explicativ", ""),
        })

    return {
        "exportat_la": datetime.now().isoformat(timespec="seconds"),
        "proiect": "Logistica Vietii",
        "metadata": metadata or {},
        "date_intrare": input_payload,
        "rezultate": {
            "numar_iteratii": len(states),
            "cost_optim": compute_transport_cost(states[-1]) if states else None,
            "stari": exported_states,
        },
        "interpretare_model": interpretation,
    }

def interpret_with_decision_tree(
    cost: list[list[float]],
    supply: list[float],
    demand: list[float],
    states: list[dict[str, Any]],
    source_labels: list[str],
    destination_labels: list[str],
) -> dict[str, Any]:
    final_state = states[-1]
    total_supply = sum(supply)
    total_demand = sum(demand)
    balanced = abs(total_supply - total_demand) < 1e-9
    initial_cost = compute_transport_cost(states[0]) if states else 0.0
    final_cost = compute_transport_cost(final_state)
    economy = ((initial_cost - final_cost) / initial_cost * 100) if initial_cost else 0.0

    lowered_labels = [label.lower() for label in destination_labels]
    tumor_index = next(
        (idx for idx, label in enumerate(lowered_labels) if any(token in label for token in ("tumor", "tumora", "neoplasm", "cancer"))),
        None,
    )

    column_means = []
    for j in range(len(demand)):
        column_means.append(sum(row[j] for row in cost) / max(len(cost), 1))

    if tumor_index is None and len(demand) >= 5:
        min_col = min(range(len(column_means)), key=lambda idx: column_means[idx])
        med = statistics.median(column_means)
        if med and column_means[min_col] <= med * 0.72:
            tumor_index = min_col

    coverage = []
    total_deficit = 0.0
    tumor_flow = 0.0
    organ_flow = 0.0

    for j, needed in enumerate(demand):
        delivered = 0.0
        deficit = 0.0
        for (i, col), quantity in final_state["alocari"].items():
            if col != j:
                continue
            if i < final_state["original_m"]:
                delivered += quantity.real
            else:
                deficit += quantity.real

        if j == tumor_index:
            tumor_flow += delivered
        else:
            organ_flow += delivered
        total_deficit += deficit
        coverage.append({
            "destinatie": destination_labels[j],
            "necesar": needed,
            "acoperit": delivered,
            "deficit": deficit,
            "acoperire_procente": (delivered / needed * 100) if needed else 100.0,
        })

    tumor_advantage = False
    if tumor_index is not None and column_means:
        tumor_advantage = column_means[tumor_index] <= statistics.median(column_means) * 0.8

    tumor_share = tumor_flow / max(tumor_flow + organ_flow, 1e-9)
    deficit_share = total_deficit / max(total_demand, 1e-9)

    if total_deficit > 0 and tumor_index is not None:
        verdict = "Patologic critic"
        rule = "deficit_vital > 0 si exista punct de consum parazit"
    elif tumor_index is not None and (tumor_share >= 0.18 or tumor_advantage):
        verdict = "Patologic oncologic"
        rule = "tumora are cost logistic redus sau capteaza o pondere mare din flux"
    elif not balanced or total_deficit > 0:
        verdict = "Dezechilibru homeostatic"
        rule = "cererea si oferta nu sunt complet echilibrate"
    else:
        verdict = "Fiziologic stabil"
        rule = "cerere acoperita integral si fara consum parazit detectat"

    risk_score = min(100, round(deficit_share * 55 + tumor_share * 35 + (10 if tumor_advantage else 0), 1))

    weakest_coverages = sorted(coverage, key=lambda item: (item["acoperire_procente"], -item["deficit"]))
    critical_targets = [item["destinatie"] for item in weakest_coverages[:2] if item["acoperire_procente"] < 100]
    target_text = ", ".join(critical_targets) if critical_targets else "organele sanatoase"
    oncology_monitoring_text = (
        f"Monitorizati daca destinatiile sanatoase precum {target_text} isi mentin acoperirea dupa reducerea fluxului tumoral."
        if critical_targets
        else "Monitorizati daca organele sanatoase isi mentin acoperirea dupa reducerea fluxului tumoral."
    )

    recommendations: list[str] = []

    if verdict == "Patologic critic":
        recommendations.extend([
            f"Prioritizati imediat destinatiile cu deficit major ({target_text}) prin praguri minime de acoperire sau costuri penalizatoare pentru subalimentare.",
            "Reduceti atractivitatea rutelor catre tumora pentru a simula o interventie anti-angiogenica si a elibera resurse pentru zonele vitale.",
            "Rulati scenarii alternative cu cresterea ofertei totale sau redistribuirea surselor pentru a testa daca deficitul critic poate fi eliminat.",
        ])
    elif verdict == "Patologic oncologic":
        recommendations.extend([
            "Cresteti costul rutelor catre tumora sau limitati explicit fluxul maxim admis pentru a reduce consumul parazit.",
            oncology_monitoring_text,
            "Introduceti cereri dinamice in timp pentru a urmari daca avantajul tumoral persista pe mai multe iteratii clinice simulate.",
        ])
    elif verdict == "Dezechilibru homeostatic":
        recommendations.extend([
            "Reechilibrati raportul dintre oferta si cerere astfel incat solverul sa nu mai introduca deficit sau entitati fictive in solutie.",
            f"Verificati configuratia costurilor pentru destinatiile cu acoperire slaba ({target_text}) si redistribuiti sursele mai eficient.",
            "Testati praguri minime de acoperire pe organele critice pentru a stabiliza sistemul in scenariile viitoare.",
        ])
    else:
        recommendations.extend([
            "Pastrati configuratia actuala ca scenariu de referinta si comparati noile simulari fata de aceasta baza fiziologica stabila.",
            "Monitorizati periodic ponderea fluxului catre fiecare destinatie pentru a detecta devreme aparitia unui consum parazit.",
            "Extindeti modelul cu cereri dinamice sau factori temporali pentru a verifica daca stabilitatea se mentine in scenarii evolutive.",
        ])

    if tumor_index is not None and tumor_advantage and verdict != "Patologic critic":
        recommendations.append(
            "Avantajul logistic al tumorii ramane prezent; analizati rutele cu cost minim catre aceasta destinatie si testati penalizari tintite."
        )

    if economy < 5:
        recommendations.append(
            "Economia obtinuta prin optimizare este redusa; merita testata o reconfigurare a matricii de costuri sau a distributiei initiale a ofertei."
        )

    if risk_score >= 70:
        risk_level = "ridicat"
    elif risk_score >= 35:
        risk_level = "mediu"
    else:
        risk_level = "scazut"

    if verdict == "Patologic critic":
        user_title = "Resursele nu ajung suficient acolo unde este nevoie."
        user_summary = (
            "Dupa optimizare, sistemul ramane intr-o stare critica: unele destinatii importante nu isi acopera complet necesarul, "
            "iar tumora continua sa atraga o parte din resurse."
        )
        user_highlights = [
            f"Destinatiile cu cea mai slaba acoperire sunt: {target_text}.",
            f"Tumora primeste aproximativ {round(tumor_share * 100)}% din fluxul distribuit.",
            f"Scorul de risc este {risk_score}/100, adica un nivel {risk_level}.",
        ]
    elif verdict == "Patologic oncologic":
        user_title = "Sistemul functioneaza, dar tumora atrage prea multe resurse."
        user_summary = (
            "Organismul simulat isi acopera in mare parte nevoile, dar tumora are un avantaj si capteaza un flux prea mare fata de restul destinatiilor."
        )
        user_highlights = [
            f"Tumora primeste aproximativ {round(tumor_share * 100)}% din fluxul total util.",
            "Nu apare un deficit critic imediat, dar distributia este inclinata in favoarea tumorii.",
            f"Scorul de risc este {risk_score}/100, adica un nivel {risk_level}.",
        ]
    elif verdict == "Dezechilibru homeostatic":
        user_title = "Distributia resurselor nu este inca bine echilibrata."
        user_summary = (
            "Programul a gasit o solutie de transport, dar sistemul nu este suficient de stabil: cererea, oferta sau acoperirea pe destinatii nu sunt bine armonizate."
        )
        user_highlights = [
            f"Zonele care trebuie urmarite mai atent sunt: {target_text}.",
            "Problema principala este dezechilibrul general al distributiei, nu un consum tumoral dominant.",
            f"Scorul de risc este {risk_score}/100, adica un nivel {risk_level}.",
        ]
    else:
        user_title = "Distributia este stabila si apropiata de functionarea normala."
        user_summary = (
            "Dupa rularea programului, toate destinatiile isi primesc necesarul, iar sistemul nu arata semne clare de consum parazit sau dezechilibru major."
        )
        user_highlights = [
            "Cererea este acoperita complet sau aproape complet in toate punctele importante.",
            "Nu exista un semnal care sa arate ca tumora atrage resurse in mod problematic.",
            f"Scorul de risc este {risk_score}/100, adica un nivel {risk_level}.",
        ]

    return {
        "model_ales": "Arbore decizional explicabil (Decision Tree)",
        "verdict": verdict,
        "regula_decizie": rule,
        "scor_risc": risk_score,
        "nivel_risc": risk_level,
        "rezumat_utilizator": {
            "titlu": user_title,
            "mesaj": user_summary,
            "puncte": user_highlights,
        },
        "echilibru": {
            "oferta_totala": total_supply,
            "cerere_totala": total_demand,
            "sistem_echilibrat": balanced,
        },
        "eficienta": {
            "cost_initial": initial_cost,
            "cost_optim": final_cost,
            "economie_efort_procente": round(economy, 2),
        },
        "tumora": {
            "detectata": tumor_index is not None,
            "destinatie": destination_labels[tumor_index] if tumor_index is not None else None,
            "flux_primit": tumor_flow,
            "pondere_flux": round(tumor_share * 100, 2),
            "avantaj_angiogenic": tumor_advantage,
        },
        "acoperire_destinatii": coverage,
        "recomandari": recommendations,
    }

def _register_custom_fonts():

    base = Path(__file__).resolve().parents[1]
    parent = base.parent

    font_map = {
        "CardoBold": ["Cardo-Bold.ttf"],
        "TTForsLight": ["TT Fors Trial Light.ttf"],
    }
    for font_name, filenames in font_map.items():
        for fn in filenames:
            for search_dir in [base, parent]:
                candidate = search_dir / fn
                if candidate.exists():
                    try:
                        pdfmetrics.registerFont(TTFont(font_name, str(candidate)))
                    except Exception:
                        pass
                    break

def _rl_color(hex_str: str) -> rl_colors.Color:

    h = hex_str.lstrip("#")
    return rl_colors.Color(int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)

def _strip_diacritics(text: Any) -> Any:

    if not isinstance(text, str):
        return text
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char))

def _strip_diacritics_deep(value: Any) -> Any:
    if isinstance(value, dict):
        return { _strip_diacritics(k): _strip_diacritics_deep(v) for k, v in value.items() }
    if isinstance(value, list):
        return [_strip_diacritics_deep(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_strip_diacritics_deep(item) for item in value)
    return _strip_diacritics(value)

def _format_ro_datetime(value: Any) -> str:

    try:
        ro_tz = ZoneInfo("Europe/Bucharest")
    except ZoneInfoNotFoundError:
        ro_tz = datetime.now().astimezone().tzinfo

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw.replace("T", " ")
    else:
        dt = datetime.now().astimezone(ro_tz)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ro_tz)
    else:
        dt = dt.astimezone(ro_tz)

    return dt.strftime("%d.%m.%Y %H:%M:%S")

_C_DARK = _rl_color("#1A0A0E")
_C_PANEL = _rl_color("#2D1218")
_C_CARD = _rl_color("#F7ECE4")
_C_PINK = _rl_color("#B65B62")
_C_GOLD = _rl_color("#C9A15A")
_C_TEAL = _rl_color("#4AA6A0")
_C_GREEN = _rl_color("#2E8B57")
_C_TEXT = _rl_color("#33181B")
_C_WHITE = rl_colors.white
_C_LIGHT_BG = _rl_color("#FFF8F2")
_C_BORDER = _rl_color("#E6D2C6")

def _get_styles():

    _register_custom_fonts()

    body_font = "TTForsLight" if "TTForsLight" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    title_font = "CardoBold" if "CardoBold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"

    return {
        "title": ParagraphStyle("Title", fontName=title_font, fontSize=28, leading=34,
                                textColor=_C_TEXT, alignment=TA_CENTER, spaceAfter=6),
        "subtitle": ParagraphStyle("Subtitle", fontName=body_font, fontSize=14, leading=18,
                                   textColor=_C_PINK, alignment=TA_CENTER, spaceAfter=14),
        "h1": ParagraphStyle("H1", fontName=title_font, fontSize=18, leading=22,
                             textColor=_C_TEXT, spaceBefore=18, spaceAfter=8),
        "h2": ParagraphStyle("H2", fontName=title_font, fontSize=14, leading=18,
                             textColor=_C_PINK, spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("Body", fontName=body_font, fontSize=11, leading=15,
                               textColor=_C_TEXT, spaceAfter=4),
        "body_small": ParagraphStyle("BodySmall", fontName=body_font, fontSize=9, leading=12,
                                     textColor=_C_TEXT, spaceAfter=2),
        "accent": ParagraphStyle("Accent", fontName=title_font, fontSize=12, leading=16,
                                 textColor=_C_TEAL, spaceAfter=4),
        "meta": ParagraphStyle("Meta", fontName=body_font, fontSize=10, leading=13,
                               textColor=_rl_color("#62545A"), alignment=TA_CENTER, spaceAfter=2),
        "hero_meta": ParagraphStyle("HeroMeta", fontName=body_font, fontSize=11, leading=15,
                                    textColor=_C_TEXT, alignment=TA_CENTER, spaceAfter=4),
        "card_title": ParagraphStyle("CardTitle", fontName=title_font, fontSize=12, leading=15,
                                     textColor=_C_TEXT, alignment=TA_CENTER, spaceAfter=2),
        "card_value": ParagraphStyle("CardValue", fontName=title_font, fontSize=18, leading=22,
                                     textColor=_C_PINK, alignment=TA_CENTER, spaceAfter=2),
        "chart_caption": ParagraphStyle("ChartCaption", fontName=body_font, fontSize=10, leading=14,
                                        textColor=_rl_color("#62545A"), alignment=TA_LEFT, spaceAfter=4),
    }

def _make_table(data_rows, col_widths=None, header=True):

    t = Table(data_rows, colWidths=col_widths, repeatRows=1 if header else 0)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _C_PINK),
        ("TEXTCOLOR", (0, 0), (-1, 0), _C_WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), _C_TEXT),
        ("GRID", (0, 0), (-1, -1), 0.4, _rl_color("#CFAE9E")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    for i in range(1, len(data_rows)):
        bg = _C_CARD if i % 2 == 0 else _C_LIGHT_BG
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

    t.setStyle(TableStyle(style_cmds))
    return t

def _draw_pdf_chrome(canvas, doc):

    canvas.saveState()
    page_w, page_h = doc.pagesize

    canvas.setFillColor(_C_LIGHT_BG)
    canvas.rect(0, 0, page_w, page_h, stroke=0, fill=1)

    canvas.setStrokeColor(_C_PINK)
    canvas.setLineWidth(0.8)
    canvas.line(doc.leftMargin, page_h - 0.95 * cm, page_w - doc.rightMargin, page_h - 0.95 * cm)

    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(_rl_color("#705E63"))
    canvas.drawString(doc.leftMargin, 0.7 * cm, "Logistica Vietii - raport generat automat")
    canvas.drawRightString(page_w - doc.rightMargin, 0.7 * cm, f"Pagina {canvas.getPageNumber()}")

    canvas.restoreState()

def _make_metric_cards(metrics: list[tuple[str, str]], usable_width: float, styles: dict[str, ParagraphStyle]) -> Table:

    cols = len(metrics)
    col_width = usable_width / max(cols, 1)
    cells = []
    for label, value in metrics:
        cells.append(
            Paragraph(
                f"<para align='center'><font color='#62545A' size='9'>{label}</font><br/><font color='#B65B62' size='18'><b>{value}</b></font></para>",
                styles["body"],
            )
        )

    table = Table([cells], colWidths=[col_width] * cols)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_CARD),
        ("BOX", (0, 0), (-1, -1), 0.8, _C_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, _C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table

def _make_hero_panel(lines: list[str], usable_width: float, styles: dict[str, ParagraphStyle]) -> Table:
    content = [Paragraph(line, styles["hero_meta"]) for line in lines if line]
    table = Table([[content]], colWidths=[usable_width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _C_CARD),
        ("BOX", (0, 0), (-1, -1), 0.8, _C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
    ]))
    return table

def _message_to_lines(message: str) -> list[str]:
    return [line.strip() for line in message.replace("\n", " ").split(". ") if line.strip()]

def export_pdf_report(
    payload: dict[str, Any],
    file_path: str,
    logo_path: str | None = None,
    chart_images: list[bytes] | None = None,
    chart_images_are_cards: bool = False,
):
    payload = _strip_diacritics_deep(payload)
    styles = _get_styles()
    page_w, page_h = A4

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        topMargin=2.25 * cm,
        bottomMargin=1.7 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        title="Logistica Vietii - Raport Complet",
        author="Logistica Vietii App",
    )

    story = []
    usable_width = page_w - 3.6 * cm

    story.append(Spacer(1, 5 * cm))

    if logo_path and Path(logo_path).exists():
        try:
            story.append(RLImage(logo_path, width=8 * cm, height=2.5 * cm))
            story.append(Spacer(1, 0.8 * cm))
        except Exception:
            pass

    story.append(Paragraph("Logistica Vietii", styles["title"]))
    story.append(Paragraph(
        "Analiza și Optimizarea Fluxurilor de Distribuție",
        styles["subtitle"]
    ))
    story.append(Spacer(1, 0.12 * cm))
    story.append(HRFlowable(width="60%", thickness=1.5, color=_C_PINK, spaceAfter=10, spaceBefore=2))

    meta = payload.get("metadata", {})
    hero_lines = []
    if meta.get("scenariu"):
        hero_lines.append(f"<b>Scenariu analizat:</b> {meta['scenariu']}")
    if meta.get("note"):
        hero_lines.append(f"<b>Observatii:</b> {meta['note']}")
    if hero_lines:
        story.append(_make_hero_panel(hero_lines, usable_width, styles))

    interp = payload.get("interpretare_model") or {}
    rez = payload.get("rezultate", {})
    metric_cards = _make_metric_cards(
        [
            ("Cost optim", f"{rez.get('cost_optim', 0):g} UM" if rez.get("cost_optim") is not None else "-"),
            ("Iteratii", str(rez.get("numar_iteratii", 0))),
            ("Verdict", str(interp.get("verdict", "-"))),
            ("Scor risc", f"{interp.get('scor_risc', 0)}/100" if interp else "-"),
        ],
        usable_width,
        styles,
    )
    export_time = _format_ro_datetime(
        payload.get("exportat_la", datetime.now().astimezone())
    )

    logo_height_estimate = 3.3 * cm if logo_path and Path(logo_path).exists() else 0
    hero_panel_height_estimate = ((0.9 + 0.48 * len(hero_lines)) * cm) if hero_lines else 0
    title_block_estimate = 3.6 * cm
    top_block_estimate = 5 * cm + logo_height_estimate + title_block_estimate + hero_panel_height_estimate
    bottom_block_estimate = 2.9 * cm
    usable_page_height = page_h - doc.topMargin - doc.bottomMargin
    push_to_bottom = max(0.2 * cm, usable_page_height - top_block_estimate - bottom_block_estimate - 1.2 * cm)

    story.append(Spacer(1, push_to_bottom))
    story.append(metric_cards)
    story.append(Spacer(1, 0.18 * cm))
    story.append(Paragraph(f"Raport generat la: {export_time}", styles["meta"]))
    story.append(PageBreak())

    story.append(Paragraph("1. Date de Intrare", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.8, color=_C_PINK, spaceAfter=8))

    di = payload.get("date_intrare", {})
    surse = di.get("surse", [])
    destinatii = di.get("destinatii", [])
    matrice = di.get("matrice_costuri", [])
    disponibil = di.get("disponibil", [])
    necesar = di.get("necesar", [])

    if matrice:
        header_row = [""] + destinatii + ["Disponibil"]
        rows = [header_row]
        for i, src in enumerate(surse):
            row = [src] + [f"{c:g}" for c in matrice[i]]
            row.append(f"{disponibil[i]:g}" if i < len(disponibil) else "")
            rows.append(row)
        rows.append(["Necesar"] + [f"{n:g}" for n in necesar] + [f"{sum(necesar):g}"])

        n_cols = len(header_row)
        col_w = min(usable_width / n_cols, 2.8 * cm)
        t = _make_table(rows, col_widths=[col_w] * n_cols)
        story.append(t)

    story.append(Spacer(1, 0.5 * cm))

    stari = payload.get("rezultate", {}).get("stari", [])
    if stari:
        story.append(Paragraph("2. Iteratii ale Algoritmului MODI", styles["h1"]))
        story.append(HRFlowable(width="100%", thickness=0.8, color=_C_PINK, spaceAfter=8))

        for st in stari:
            it_num = st["iteratie"]
            is_opt = st.get("este_optim", False)
            cost_real = st.get("cost_transport_real", "?")

            title_text = f"Iteratia {it_num}" + (" - SOLUTIE OPTIMA" if is_opt else "")
            story.append(Paragraph(title_text, styles["h2"]))
            story.append(Paragraph(f"Cost transport la acest pas: <b>{cost_real:g}</b> UM", styles["body"]))

            alocari = st.get("alocari", {})
            if alocari:
                alloc_header = ["Ruta", "Cantitate alocata"]
                alloc_rows = [alloc_header]
                for ruta, info in alocari.items():
                    val = info.get("valoare", "?") if isinstance(info, dict) else str(info)
                    alloc_rows.append([ruta, val])
                if len(alloc_rows) > 1:
                    at = _make_table(alloc_rows, col_widths=[4 * cm, 3 * cm])
                    story.append(at)
                    story.append(Spacer(1, 2 * mm))

            u_vals = st.get("u", [])
            v_vals = st.get("v", [])
            if u_vals and v_vals:
                uv_text = f"<b>u</b> = [{', '.join(f'{x:g}' for x in u_vals)}] &nbsp;&nbsp; <b>v</b> = [{', '.join(f'{x:g}' for x in v_vals)}]"
                story.append(Paragraph(uv_text, styles["body_small"]))

            delta = st.get("delta", {})
            if delta:
                neg_deltas = {k: v for k, v in delta.items() if v < 0}
                if neg_deltas:
                    nd_text = ", ".join(f"{k}: {v:g}" for k, v in neg_deltas.items())
                    story.append(Paragraph(f"<b>Costuri marginale negative:</b> {nd_text}", styles["body_small"]))

            mesaj = st.get("mesaj_explicativ", "")
            if mesaj:
                story.append(Spacer(1, 2 * mm))
                for line in _message_to_lines(mesaj):
                    story.append(Paragraph(f"• {line if line.endswith('.') else line + '.'}", styles["body_small"]))

            story.append(Spacer(1, 4 * mm))

    cost_optim = rez.get("cost_optim")
    nr_iteratii = rez.get("numar_iteratii", 0)

    story.append(PageBreak())
    story.append(Paragraph("3. Solutia Optima", styles["h1"]))
    story.append(HRFlowable(width="100%", thickness=0.8, color=_C_GREEN, spaceAfter=8))

    if cost_optim is not None:
        story.append(Paragraph(
            f"Cost total minim: <b>{cost_optim:g} UM</b> &nbsp; | &nbsp; Iteratii necesare: <b>{nr_iteratii}</b>",
            styles["accent"]
        ))

    if interp:
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("4. Interpretare Doctor AI", styles["h1"]))
        story.append(HRFlowable(width="100%", thickness=0.8, color=_C_GOLD, spaceAfter=8))

        story.append(Paragraph(f"<b>Model:</b> {interp.get('model_ales', '?')}", styles["body"]))
        story.append(Paragraph(f"<b>Verdict:</b> {interp.get('verdict', '?')}", styles["body"]))
        story.append(Paragraph(f"<b>Scor risc:</b> {interp.get('scor_risc', '?')}/100", styles["body"]))
        story.append(Paragraph(f"<b>Regula decizie:</b> {interp.get('regula_decizie', '?')}", styles["body"]))

        eff = interp.get("eficienta", {})
        if eff:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Eficienta sistemului", styles["h2"]))
            story.append(Paragraph(
                f"Cost initial: <b>{eff.get('cost_initial', '?'):g} UM</b> -> "
                f"Cost optim: <b>{eff.get('cost_optim', '?'):g} UM</b> -> "
                f"Economie: <b>{eff.get('economie_efort_procente', 0):.1f}%</b>",
                styles["body"]
            ))

        tumor = interp.get("tumora", {})
        if tumor and tumor.get("detectata"):
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Punct de consum parazit (Tumora)", styles["h2"]))
            story.append(Paragraph(
                f"Destinatie: <b>{tumor.get('destinatie', '?')}</b> | "
                f"Flux primit: <b>{tumor.get('flux_primit', 0):g}</b> | "
                f"Pondere: <b>{tumor.get('pondere_flux', 0):g}%</b> | "
                f"Avantaj angiogenic: <b>{'Da' if tumor.get('avantaj_angiogenic') else 'Nu'}</b>",
                styles["body"]
            ))

        coverage = interp.get("acoperire_destinatii", [])
        if coverage:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Acoperire pe destinatii", styles["h2"]))
            cov_header = ["Destinatie", "Necesar", "Acoperit", "Deficit", "Acoperire %"]
            cov_rows = [cov_header]
            for item in coverage:
                cov_rows.append([
                    item.get("destinatie", ""),
                    f"{item.get('necesar', 0):g}",
                    f"{item.get('acoperit', 0):g}",
                    f"{item.get('deficit', 0):g}",
                    f"{item.get('acoperire_procente', 0):.1f}%",
                ])
            ct = _make_table(cov_rows, col_widths=[3.5 * cm, 2 * cm, 2 * cm, 2 * cm, 2.5 * cm])
            story.append(ct)

        recs = interp.get("recomandari", [])
        if recs:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph("Strategii logistice recomandate", styles["h2"]))
            for idx, rec in enumerate(recs, 1):
                story.append(Paragraph(f"{idx}. {rec}", styles["body"]))

    if chart_images:
        story.append(PageBreak())
        story.append(Paragraph("5. Grafice Analitice", styles["h1"]))
        story.append(HRFlowable(width="100%", thickness=0.8, color=_C_TEAL, spaceAfter=8))

        chart_titles = [
            "Evolutia costului total",
            "Acoperirea destinatiilor",
            "Harta rutelor active",
        ]
        chart_descriptions = [
            "Curba urmareste scaderea costului dupa fiecare iteratie, cu accent pe punctul de pornire si solutia optima.",
            "Fiecare bara arata cat s-a distribuit fata de necesar, ca sa vezi rapid unde exista deficit sau acoperire completa.",
            "Reteaua evidentiaza doar conexiunile care transporta efectiv flux, iar grosimea traseului arata intensitatea rutei.",
        ]

        temp_files = []
        for idx, img_bytes in enumerate(chart_images):
            if idx < len(chart_titles) and not chart_images_are_cards:
                story.append(Paragraph(chart_titles[idx], styles["h2"]))
                story.append(Paragraph(chart_descriptions[idx], styles["chart_caption"]))

            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.write(img_bytes)
            tmp.close()
            temp_files.append(tmp.name)

            try:
                image_width = usable_width
                img_reader = ImageReader(tmp.name)
                raw_width, raw_height = img_reader.getSize()
                aspect_ratio = raw_height / max(raw_width, 1)
                image_height = image_width * aspect_ratio
                img = RLImage(tmp.name, width=image_width, height=image_height)
                if chart_images_are_cards:
                    story.append(img)
                else:
                    frame = Table([[img]], colWidths=[usable_width])
                    frame.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), _C_PANEL),
                        ("BOX", (0, 0), (-1, -1), 0.8, _C_BORDER),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ]))
                    story.append(frame)
            except Exception:
                story.append(Paragraph("[Graficul nu a putut fi inserat]", styles["body_small"]))

            story.append(Spacer(1, 0.5 * cm))
    else:
        temp_files = []

    doc.build(story, onFirstPage=_draw_pdf_chrome, onLaterPages=_draw_pdf_chrome)

    for tmp_path in temp_files:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
