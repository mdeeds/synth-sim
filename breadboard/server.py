#!/usr/bin/env python3
"""Serve the breadboard UI and persist layouts beside a SPICE circuit."""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


APP_DIR = Path(__file__).resolve().parent
DEFAULT_CIRCUIT = APP_DIR.parent / "circuits" / "sawtooth" / "sawtooth.cir"
INCLUDE_RE = re.compile(r"^\s*\.include\s+['\"]?([^'\"\s]+)", re.IGNORECASE)
SUBCKT_RE = re.compile(r"^\s*\.subckt\s+(\S+)\s+(.*)", re.IGNORECASE)


def load_circuit(circuit_path: Path) -> dict:
    circuit_path = circuit_path.resolve(strict=True)
    if not circuit_path.is_file() or circuit_path.suffix.lower() != ".cir":
        raise ValueError("The circuit must be an existing .cir file.")

    text = circuit_path.read_text(encoding="utf-8-sig")
    subcircuits: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = INCLUDE_RE.match(line)
        if not match:
            continue
        include_path = (circuit_path.parent / match.group(1)).resolve(strict=True)
        for model_line in include_path.read_text(encoding="utf-8-sig").splitlines():
            subckt = SUBCKT_RE.match(model_line)
            if not subckt:
                continue
            tokens = subckt.group(2).split()
            pins = []
            for token in tokens:
                if token.lower() == "params:":
                    break
                pins.append(token)
            subcircuits[subckt.group(1).lower()] = pins

    layout_path = circuit_path.with_suffix(".layout.json")
    layout = {}
    if layout_path.exists():
        try:
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError(f"Could not load {layout_path.name}: {error}") from error
        if not isinstance(layout, dict):
            raise ValueError(f"{layout_path.name} must contain a JSON object.")

    return {
        "circuitName": circuit_path.name,
        "circuitText": text,
        "subcircuits": subcircuits,
        "layout": layout,
    }


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "BreadboardServer/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/state":
            self.send_json(self.server.state)
            return
        if path == "/":
            self.serve_file(APP_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path in ("/app.js", "/styles.css"):
            file_path = APP_DIR / path.lstrip("/")
            content_type = "text/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8"
            self.serve_file(file_path, content_type)
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/layout":
            self.send_error(404, "Not found")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("Layout payload must be between 1 byte and 1 MB.")
            layout = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(layout, dict) or layout.get("version") != 2:
                raise ValueError("Layout must be a version 2 JSON object.")
            components = layout.get("components")
            bridges = layout.get("bridges")
            if not isinstance(components, dict) or not isinstance(bridges, dict):
                raise ValueError("Layout components and bridges must be objects.")
            for component in components.values():
                if (
                    not isinstance(component, dict)
                    or not isinstance(component.get("column"), int)
                    or isinstance(component.get("column"), bool)
                    or not 0 <= component["column"] < 50
                    or not isinstance(component.get("row"), int)
                    or isinstance(component.get("row"), bool)
                    or not 0 <= component["row"] <= 4
                    or component.get("bank") not in ("top", "bottom", "ic")
                    or ("flipped" in component and not isinstance(component["flipped"], bool))
                    or ("vertical" in component and not isinstance(component["vertical"], bool))
                    or (
                        component.get("bank") == "ic"
                        and (component.get("flipped") is True or component.get("vertical") is True)
                    )
                ):
                    raise ValueError("Each component position needs a valid grid column, row, and bank.")
            for position in bridges.values():
                if not isinstance(position, int) or isinstance(position, bool) or not 0 <= position < 50:
                    raise ValueError("Each bridge position must be a valid grid column.")

            self.server.layout_path.write_text(
                json.dumps(layout, indent=2) + "\n", encoding="utf-8"
            )
            self.server.state["layout"] = layout
            self.send_json({"saved": True, "file": str(self.server.layout_path)})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self.send_json({"error": str(error)}, status=400)
        except OSError as error:
            self.send_json({"error": f"Could not save layout: {error}"}, status=500)

    def serve_file(self, file_path: Path, content_type: str) -> None:
        try:
            data = file_path.read_bytes()
        except OSError:
            self.send_error(404, "File not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, data: dict, status: int = 200) -> None:
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SPICE breadboard layout app.")
    parser.add_argument("--circuit", type=Path, default=DEFAULT_CIRCUIT, help="Path to a .cir file")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    args = parser.parse_args()

    state = load_circuit(args.circuit)
    server = ThreadingHTTPServer((args.host, args.port), RequestHandler)
    server.state = state
    server.layout_path = args.circuit.resolve().with_suffix(".layout.json")
    print(f"Serving {state['circuitName']} at http://{args.host}:{args.port}/")
    print(f"Layout file: {server.layout_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping breadboard server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
