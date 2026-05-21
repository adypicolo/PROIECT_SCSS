import argparse
import base64
import json
import mimetypes
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from core.data_io import (
    ImportedTransportData,
    build_export_payload,
    compute_transport_cost,
    export_pdf_report,
    interpret_with_decision_tree,
    load_transport_data,
)
from core.solver import TransportationSolver
from ui.graph_view import (
    generate_cost_evolution_chart,
    generate_flow_distribution_chart,
    generate_network_flow_chart,
    save_figure_to_bytes,
)

ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

def _first_present(data, *keys, default=None):
    normalized = {str(key).lower(): value for key, value in data.items()}
    for key in keys:
        if key.lower() in normalized:
            return normalized[key.lower()]
    return default

def _as_float(value):
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = str(value).strip().replace(" ", "")
    if not cleaned:
        raise ValueError("Valoare numerica lipsa.")
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)

def _ensure_length(labels, size, prefix):
    clean = []
    for index in range(size):
        if index < len(labels):
            value = str(labels[index]).strip()
            clean.append(value or f"{prefix}{index + 1}")
        else:
            clean.append(f"{prefix}{index + 1}")
    return clean

def _resolved_labels(base_labels, size, fallback_prefix, dummy_label):
    labels = _ensure_length(base_labels, min(len(base_labels), size), fallback_prefix)
    if len(labels) >= size:
        return labels[:size]

    extra = size - len(labels)
    for offset in range(extra):
        labels.append(dummy_label if offset == 0 else f"{dummy_label} {offset + 1}")
    return labels

def _load_logo_path():
    matches = sorted(ROOT_DIR.glob("*.png"))
    return matches[0] if matches else None

def _load_sample_payload():
    sample_path = ROOT_DIR / "exemplu_import_logistica_vietii.json"
    imported = load_transport_data(str(sample_path))
    return _dataset_from_import(imported)

def _dataset_from_import(imported: ImportedTransportData):
    return {
        "title": imported.title,
        "scenario": imported.scenario,
        "notes": imported.notes,
        "source_labels": imported.source_labels,
        "destination_labels": imported.destination_labels,
        "cost_matrix": imported.cost,
        "supply": imported.supply,
        "demand": imported.demand,
    }

def _normalize_transport_payload(data):
    cost = _first_present(data, "cost_matrix", "matrice_costuri", "cost", "costuri", "matrice")
    supply = _first_present(data, "supply", "disponibil", "oferta", "capacitate")
    demand = _first_present(data, "demand", "necesar", "cerere")

    if cost is None or supply is None or demand is None:
        raise ValueError("Payload-ul trebuie sa contina cost_matrix, supply si demand.")

    cost_matrix = [[_as_float(cell) for cell in row] for row in cost]
    supply_values = [_as_float(value) for value in supply]
    demand_values = [_as_float(value) for value in demand]

    if len(cost_matrix) != len(supply_values):
        raise ValueError("Numarul de randuri din cost_matrix nu coincide cu numarul surselor.")
    if any(len(row) != len(demand_values) for row in cost_matrix):
        raise ValueError("Numarul de coloane din cost_matrix nu coincide cu numarul destinatiilor.")

    source_labels = _ensure_length(
        _first_present(data, "source_labels", "surse", "sources", default=[]),
        len(supply_values),
        "A",
    )
    destination_labels = _ensure_length(
        _first_present(data, "destination_labels", "destinatii", "destinations", default=[]),
        len(demand_values),
        "B",
    )

    return {
        "title": str(_first_present(data, "title", "titlu", default="") or ""),
        "scenario": str(_first_present(data, "scenario", "scenariu", default="") or ""),
        "notes": str(_first_present(data, "notes", "note", "descriere", "description", default="") or ""),
        "source_labels": source_labels,
        "destination_labels": destination_labels,
        "cost_matrix": cost_matrix,
        "supply": supply_values,
        "demand": demand_values,
    }

def _load_transport_from_uploaded_text(filename, content):
    suffix = Path(filename or "dataset.json").suffix.lower() or ".json"
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=suffix, encoding="utf-8") as temp_file:
        temp_file.write(content)
        temp_path = Path(temp_file.name)

    try:
        imported = load_transport_data(str(temp_path))
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

    return _dataset_from_import(imported)

def _data_url_from_png(png_bytes):
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

def _decode_png_data_url(value):
    if not isinstance(value, str) or not value.startswith("data:image/png;base64,"):
        return None
    try:
        return base64.b64decode(value.split(",", 1)[1])
    except (ValueError, TypeError):
        return None

def _extract_pdf_chart_snapshots(payload):
    snapshots = payload.get("pdf_chart_snapshots")
    if not isinstance(snapshots, list):
        return None

    images = []
    for item in snapshots[:3]:
        decoded = _decode_png_data_url(item)
        if decoded:
            images.append(decoded)

    return images or None

def _serialize_state(state, source_labels, destination_labels):
    display_sources = _resolved_labels(source_labels, state["m"], "A", "Sursa fictiva")
    display_destinations = _resolved_labels(destination_labels, state["n"], "B", "Destinatie fictiva")

    allocations = {}
    for (row_index, col_index), quantity in state["alocari"].items():
        allocations[f"{row_index}:{col_index}"] = {
            "display": str(quantity),
            "real": quantity.real,
            "epsilon": quantity.eps,
        }

    delta_map = {
        f"{row_index}:{col_index}": value
        for (row_index, col_index), value in state["delta"].items()
    }
    cycle_order = {
        f"{row_index}:{col_index}": idx
        for idx, (row_index, col_index) in enumerate(state["circuit"] or [])
    }

    rows = []
    for row_index in range(state["m"]):
        cells = []
        for col_index in range(state["n"]):
            key = f"{row_index}:{col_index}"
            allocation = allocations.get(key)
            cycle_index = cycle_order.get(key)
            cells.append({
                "key": key,
                "cost": state["cost"][row_index][col_index],
                "allocation": allocation,
                "delta": delta_map.get(key),
                "is_pivot": state["pivot"] == (row_index, col_index),
                "is_cycle": key in cycle_order,
                "cycle_sign": "+" if cycle_index is not None and cycle_index % 2 == 0 else "-" if cycle_index is not None else None,
                "is_dummy": row_index >= state["original_m"] or col_index >= state["original_n"],
            })

        rows.append({
            "index": row_index,
            "label": display_sources[row_index],
            "u": state["u"][row_index],
            "u_display": "-" if state["u"][row_index] is None else f"{state['u'][row_index]:g}",
            "supply_display": str(state["disp"][row_index]),
            "is_dummy": row_index >= state["original_m"],
            "cells": cells,
        })

    columns = []
    for col_index in range(state["n"]):
        columns.append({
            "index": col_index,
            "label": display_destinations[col_index],
            "v": state["v"][col_index],
            "v_display": "-" if state["v"][col_index] is None else f"{state['v'][col_index]:g}",
            "demand_display": str(state["nec"][col_index]),
            "is_dummy": col_index >= state["original_n"],
        })

    total_supply = sum(state["disp"], start=type(state["disp"][0])(0))
    return {
        "iteration": state["iteratie"],
        "is_optimal": state["este_optim"],
        "transport_cost": compute_transport_cost(state),
        "message": state.get("mesaj_explicativ", ""),
        "pivot": list(state["pivot"]) if state["pivot"] is not None else None,
        "circuit": [list(cell) for cell in (state["circuit"] or [])],
        "m": state["m"],
        "n": state["n"],
        "original_m": state["original_m"],
        "original_n": state["original_n"],
        "columns": columns,
        "rows": rows,
        "total_supply_display": str(total_supply),
    }

def _solve_transport_payload(payload, include_chart_images=True):
    dataset = _normalize_transport_payload(payload)
    metadata = {
        "titlu": dataset["title"],
        "scenariu": dataset["scenario"],
        "note": dataset["notes"],
    }
    input_payload = {
        "surse": dataset["source_labels"],
        "destinatii": dataset["destination_labels"],
        "matrice_costuri": dataset["cost_matrix"],
        "disponibil": dataset["supply"],
        "necesar": dataset["demand"],
    }

    solver = TransportationSolver(dataset["cost_matrix"], dataset["supply"], dataset["demand"])

    states = []
    display_sources = _resolved_labels(dataset["source_labels"], solver.m, "A", "Sursa fictiva")
    display_destinations = _resolved_labels(dataset["destination_labels"], solver.n, "B", "Destinatie fictiva")

    for state in solver.solve():
        state["source_labels"] = display_sources
        state["destination_labels"] = display_destinations
        states.append(state)

    if not states:
        raise ValueError("Solverul nu a returnat nicio iteratie.")

    interpretation = interpret_with_decision_tree(
        dataset["cost_matrix"],
        dataset["supply"],
        dataset["demand"],
        states,
        dataset["source_labels"],
        dataset["destination_labels"],
    )

    export_payload = build_export_payload(input_payload, states, interpretation, metadata)

    chart_images = []
    charts_payload = None
    if include_chart_images:
        chart_images = [
            save_figure_to_bytes(generate_cost_evolution_chart(states)),
            save_figure_to_bytes(
                generate_flow_distribution_chart(states[-1], dataset["destination_labels"], dataset["demand"])
            ),
            save_figure_to_bytes(
                generate_network_flow_chart(states[-1], dataset["source_labels"], dataset["destination_labels"])
            ),
        ]
        charts_payload = {
            "cost_evolution": _data_url_from_png(chart_images[0]),
            "flow_distribution": _data_url_from_png(chart_images[1]),
            "network_flow": _data_url_from_png(chart_images[2]),
        }

    return {
        "input": dataset,
        "summary": {
            "iteration_count": len(states),
            "initial_cost": compute_transport_cost(states[0]),
            "optimal_cost": compute_transport_cost(states[-1]),
            "verdict": interpretation["verdict"],
            "risk_score": interpretation["scor_risc"],
            "balanced": interpretation["echilibru"]["sistem_echilibrat"],
        },
        "states": [_serialize_state(state, dataset["source_labels"], dataset["destination_labels"]) for state in states],
        "interpretation": interpretation,
        "charts": charts_payload,
        "export_payload": export_payload,
        "chart_images": chart_images,
    }

def _static_file_response(handler, file_path):
    content_type, _ = mimetypes.guess_type(str(file_path))
    content_type = content_type or "application/octet-stream"
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(file_path.read_bytes())

class WebAppHandler(BaseHTTPRequestHandler):
    server_version = "LogisticaVietiiWeb/1.0"

    def _read_json_body(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            return json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON invalid: {exc.msg}") from exc

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, payload, content_type, filename=None):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_json(self, message, status=HTTPStatus.BAD_REQUEST):
        self._send_json({"ok": False, "error": message}, status=status)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/health":
            self._send_json({"ok": True, "status": "ready"})
            return

        if path == "/api/sample":
            self._send_json({"ok": True, "dataset": _load_sample_payload()})
            return

        if path == "/assets/project-logos.png":
            logo_path = _load_logo_path()
            if logo_path and logo_path.exists():
                _static_file_response(self, logo_path)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
            return

        if path in {"/", "/web", "/web/", "/web/index.html"}:
            file_path = WEB_DIR / "index.html"
        else:
            relative_path = path.lstrip("/")
            if relative_path.startswith("web/"):
                relative_path = relative_path[4:]
            file_path = (WEB_DIR / relative_path).resolve()
            if not str(file_path).startswith(str(WEB_DIR.resolve())):
                self.send_error(HTTPStatus.FORBIDDEN)
                return

        if file_path.exists() and file_path.is_file():
            _static_file_response(self, file_path)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        try:
            payload = self._read_json_body()

            if path == "/api/import":
                filename = str(payload.get("filename") or "dataset.json")
                content = payload.get("content")
                if not isinstance(content, str):
                    raise ValueError("Campul content trebuie sa fie text.")
                dataset = _load_transport_from_uploaded_text(filename, content)
                self._send_json({"ok": True, "dataset": dataset})
                return

            if path == "/api/solve":
                result = _solve_transport_payload(payload, include_chart_images=False)
                response = {
                    "ok": True,
                    "input": result["input"],
                    "summary": result["summary"],
                    "states": result["states"],
                    "interpretation": result["interpretation"],
                }
                self._send_json(response)
                return

            if path == "/api/export/json":
                result = _solve_transport_payload(payload)
                json_bytes = json.dumps(
                    result["export_payload"],
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8")
                self._send_bytes(json_bytes, "application/json; charset=utf-8", "raport_logistica_vietii.json")
                return

            if path == "/api/export/pdf":
                result = _solve_transport_payload(payload)
                pdf_chart_snapshots = _extract_pdf_chart_snapshots(payload)
                chart_images = pdf_chart_snapshots or result["chart_images"]
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    pdf_path = Path(temp_file.name)

                try:
                    export_pdf_report(
                        result["export_payload"],
                        str(pdf_path),
                        logo_path=str(_load_logo_path()) if _load_logo_path() else None,
                        chart_images=chart_images,
                        chart_images_are_cards=bool(pdf_chart_snapshots),
                    )
                    pdf_bytes = pdf_path.read_bytes()
                finally:
                    try:
                        pdf_path.unlink()
                    except OSError:
                        pass

                self._send_bytes(pdf_bytes, "application/pdf", "raport_logistica_vietii.pdf")
                return

            self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self._send_error_json(str(exc), status=HTTPStatus.INTERNAL_SERVER_ERROR)

def main():
    parser = argparse.ArgumentParser(description="Server web pentru Logistica Vietii.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), WebAppHandler)
    print(f"Logistica Vietii Web ruleaza la http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
