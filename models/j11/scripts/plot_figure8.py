import csv
import math
import re
import sys
from pathlib import Path


CURVES = [
    ("10 mA", "VDS10"),
    ("25 mA", "VDS25"),
    ("50 mA", "VDS50"),
    ("75 mA", "VDS75"),
    ("100 mA", "VDS100"),
    ("125 mA", "VDS125"),
]
COLORS = ["#202020", "#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e"]


def read_ascii_raw(path):
    text = path.read_text(encoding="ascii", errors="replace")
    header, separator, values = text.partition("Values:")
    if not separator:
        raise ValueError(f"{path} is not an ASCII LTspice raw file")

    variables = {}
    in_variables = False
    for line in header.splitlines():
        if line.strip() == "Variables:":
            in_variables = True
            continue
        if in_variables:
            match = re.match(r"\s*\d+\s+(\S+)", line)
            if match:
                variables[match.group(1).lower()] = len(variables)

    rows = []
    row = None
    for line in values.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0].isdigit() and len(fields) >= 2:
            if row is not None:
                rows.append(row)
            row = [float(value) for value in fields[1:]]
        elif row is not None:
            row.extend(float(value) for value in fields)
    if row is not None:
        rows.append(row)

    if not rows or "v(g)" not in variables:
        raise ValueError(f"No sweep data or V(G) variable found in {path}")
    expected_width = len(variables)
    if any(len(point) != expected_width for point in rows):
        raise ValueError(f"Unexpected ASCII raw data row width in {path}")
    return variables, rows


def resistance_curve(variables, rows, source):
    current_index = variables[f"i({source.lower()})"]
    gate_index = variables["v(g)"]
    points = []
    for row in rows:
        current = row[current_index]
        resistance = -0.1 / current if current < 0 else math.inf
        if math.isfinite(resistance) and 0 < resistance <= 200:
            points.append((max(0.0, -row[gate_index]), resistance))
    return points


def validate_default_model(variables, rows):
    gate_index = variables["v(g)"]
    on_current_index = variables["i(vdsj111_on)"]
    idss_current_index = variables["i(vdsj111_idss)"]
    zero_gate = next((row for row in rows if abs(row[gate_index]) < 1e-12), None)
    if zero_gate is None:
        raise ValueError("No VGS=0 point found for the default J111 model checks")

    on_current = -zero_gate[on_current_index]
    idss = -zero_gate[idss_current_index]
    if on_current <= 0:
        raise ValueError("Default model produced no positive drain current at VDS=0.1 V")
    on_resistance = 0.1 / on_current
    if on_resistance > 30:
        raise ValueError(f"Default model violates the 30-ohm on-resistance limit: {on_resistance:.3f} ohm")
    if idss < 0.020:
        raise ValueError(f"Default model violates the 20-mA minimum IDSS: {idss * 1000:.3f} mA")
    print(f"Default J111 check: RDS(on)={on_resistance:.2f} ohm, IDSS={idss * 1000:.2f} mA")


def write_csv(path, curves):
    headers = ["|VGS| (V)"] + [f"RDS(on), IDSS={label} (ohm)" for label, _ in CURVES]
    samples = {}
    for index, (_, _) in enumerate(CURVES):
        for gate, resistance in curves[index]:
            samples.setdefault(round(gate, 9), [None] * len(CURVES))[index] = resistance

    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(headers)
        for gate in sorted(samples):
            writer.writerow(
                [f"{gate:.3f}"]
                + ["" if value is None else f"{value:.6f}" for value in samples[gate]]
            )


def write_svg(path, curves):
    width, height = 900, 630
    left, top, right, bottom = 105, 55, 30, 100
    plot_width = width - left - right
    plot_height = height - top - bottom

    def x_pixel(value):
        return left + value / 8 * plot_width

    def y_pixel(value):
        return top + (200 - value) / 200 * plot_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="450" y="28" text-anchor="middle" font-family="Arial" font-size="19" font-weight="bold">J111-D Figure 8: Effect of Gate-Source Voltage on Drain-Source Resistance</text>',
    ]

    for voltage in range(9):
        x = x_pixel(voltage)
        parts.extend(
            [
                f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}" stroke="#d0d0d0"/>',
                f'<text x="{x:.2f}" y="{top + plot_height + 24}" text-anchor="middle" font-family="Arial" font-size="13">{voltage}</text>',
            ]
        )
    for resistance in range(0, 201, 20):
        y = y_pixel(resistance)
        parts.extend(
            [
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#d0d0d0"/>',
                f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial" font-size="13">{resistance}</text>',
            ]
        )

    parts.extend(
        [
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="black" stroke-width="2"/>',
            f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="black" stroke-width="2"/>',
            f'<text x="{left + plot_width / 2:.2f}" y="{height - 62}" text-anchor="middle" font-family="Arial" font-size="16">|VGS|, reverse gate-source voltage (V)</text>',
            f'<text x="25" y="{top + plot_height / 2:.2f}" transform="rotate(-90 25 {top + plot_height / 2:.2f})" text-anchor="middle" font-family="Arial" font-size="16">RDS(on), drain-source resistance (ohm)</text>',
        ]
    )

    legend_x, legend_y = left + plot_width - 115, top + 16
    for index, ((label, _), color) in enumerate(zip(CURVES, COLORS)):
        points = curves[index]
        if points:
            path_data = " ".join(
                ("M" if point_index == 0 else "L")
                + f"{x_pixel(gate):.2f},{y_pixel(resistance):.2f}"
                for point_index, (gate, resistance) in enumerate(points)
            )
            parts.append(
                f'<path d="{path_data}" fill="none" stroke="{color}" stroke-width="3"/>'
            )
        y = legend_y + index * 23
        parts.extend(
            [
                f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 22}" y2="{y}" stroke="{color}" stroke-width="3"/>',
                f'<text x="{legend_x + 28}" y="{y + 5}" font-family="Arial" font-size="13">IDSS = {label}</text>',
            ]
        )

    parts.append(
        f'<text x="450" y="{height - 15}" text-anchor="middle" font-family="Arial" font-size="13">Tchannel = 25 C; VDS = 0.1 V. Typical family curves digitized approximately from the datasheet.</text>'
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def figure10_data(raw_path):
    variables, rows = read_ascii_raw(raw_path)
    gate_index = variables["v(g)"]
    zero_gate = next((row for row in rows if abs(row[gate_index]) < 1e-12), None)
    if zero_gate is None:
        raise ValueError(f"No VGS=0 point in Figure 10 LTspice output: {raw_path}")

    data = []
    for idss_label in range(10, 131, 10):
        on_index = variables[f"i(vlo{idss_label})"]
        idss_index = variables[f"i(v15_{idss_label})"]
        cutoff_index = variables[f"i(v5_{idss_label})"]
        on_current = abs(zero_gate[on_index])
        idss = abs(zero_gate[idss_index])
        if on_current <= 0 or idss <= 0:
            raise ValueError(f"Invalid current for Figure 10 {idss_label}-mA family member")

        cutoff_points = [
            (abs(row[gate_index]), abs(row[cutoff_index]))
            for row in rows
            if abs(row[cutoff_index]) > 0
        ]
        cutoff_voltage = None
        for (gate1, current1), (gate2, current2) in zip(cutoff_points, cutoff_points[1:]):
            if current1 >= 1e-6 >= current2:
                log_current1 = math.log10(current1)
                log_current2 = math.log10(current2)
                fraction = (math.log10(1e-6) - log_current1) / (log_current2 - log_current1)
                cutoff_voltage = gate1 + fraction * (gate2 - gate1)
                break
        if cutoff_voltage is None:
            raise ValueError(
                f"LTspice sweep did not cross the 1-uA cutoff criterion for {idss_label}-mA family member"
            )
        data.append((idss * 1000, 0.1 / on_current, cutoff_voltage))
    return data


def write_figure10_csv(path, data):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["IDSS (mA)", "RDS(on) at VGS=0 (ohm)", "VGS(off) (V)"])
        writer.writerows(
            (f"{idss:.6f}", f"{resistance:.6f}", f"{cutoff:.6f}")
            for idss, resistance, cutoff in data
        )


def smooth_path(points):
    commands = [f"M{points[0][0]:.2f},{points[0][1]:.2f}"]
    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]
        previous = points[max(0, index - 1)]
        following = points[min(len(points) - 1, index + 2)]
        control1 = (
            x1 + (x2 - previous[0]) / 6,
            y1 + (y2 - previous[1]) / 6,
        )
        control2 = (
            x2 - (following[0] - x1) / 6,
            y2 - (following[1] - y1) / 6,
        )
        commands.append(
            f"C{control1[0]:.2f},{control1[1]:.2f} "
            f"{control2[0]:.2f},{control2[1]:.2f} {x2:.2f},{y2:.2f}"
        )
    return " ".join(commands)


def write_figure10_svg(path, data):
    width, height = 1000, 700
    left, top, right, bottom = 125, 70, 115, 115
    plot_width = width - left - right
    plot_height = height - top - bottom

    def x_pixel(value):
        return left + (value - 10) / 140 * plot_width

    def y_pixel(value):
        return top + (100 - value) / 100 * plot_height

    resistance_points = [
        (x_pixel(current), y_pixel(resistance))
        for current, resistance, _ in data
    ]
    cutoff_points = [
        (x_pixel(current), y_pixel(cutoff * 10))
        for current, _, cutoff in data
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="500" y="35" text-anchor="middle" font-family="Arial" font-size="21" font-weight="bold">J111-D Figure 10: Effect of IDSS on RDS(on) and VGS(off)</text>',
    ]

    for current in range(10, 151, 10):
        x = x_pixel(current)
        parts.extend(
            [
                f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}" stroke="#c8c8c8"/>',
                f'<text x="{x:.2f}" y="{top + plot_height + 24}" text-anchor="middle" font-family="Arial" font-size="13">{current}</text>',
            ]
        )
    for resistance in range(0, 101, 10):
        y = y_pixel(resistance)
        parts.extend(
            [
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#c8c8c8"/>',
                f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial" font-size="13">{resistance}</text>',
                f'<text x="{left + plot_width + 12}" y="{y + 4:.2f}" text-anchor="start" font-family="Arial" font-size="13">{resistance / 10:.1f}</text>',
            ]
        )

    parts.extend(
        [
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="black" stroke-width="2"/>',
            f'<line x1="{left + plot_width}" y1="{top}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="black" stroke-width="2"/>',
            f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="black" stroke-width="2"/>',
            f'<path d="{smooth_path(resistance_points)}" fill="none" stroke="#202020" stroke-width="4"/>',
            f'<path d="{smooth_path(cutoff_points)}" fill="none" stroke="#202020" stroke-width="4"/>',
            f'<text x="{left + plot_width / 2:.2f}" y="{height - 43}" text-anchor="middle" font-family="Arial" font-size="17">IDSS, zero-gate-voltage drain current (mA)</text>',
            f'<text x="32" y="{top + plot_height / 2:.2f}" transform="rotate(-90 32 {top + plot_height / 2:.2f})" text-anchor="middle" font-family="Arial" font-size="16">rDS(on) at VGS = 0 (ohm)</text>',
            f'<text x="{width - 25}" y="{top + plot_height / 2:.2f}" transform="rotate(-90 {width - 25} {top + plot_height / 2:.2f})" text-anchor="middle" font-family="Arial" font-size="16">VGS(off) (V)</text>',
            '<text x="235" y="110" font-family="Arial" font-size="16">rDS(on) at VGS = 0</text>',
            '<line x1="370" y1="116" x2="179" y2="297" stroke="black" stroke-width="1.5" marker-end="url(#arrow)"/>',
            '<text x="690" y="370" font-family="Arial" font-size="16">VGS(off)</text>',
            '<line x1="760" y1="360" x2="559" y2="286" stroke="black" stroke-width="1.5" marker-end="url(#arrow)"/>',
            '<text x="500" y="680" text-anchor="middle" font-family="Arial" font-size="13">Typical 25 C curves digitized approximately from the datasheet; values are approximate.</text>',
        ]
    )
    parts.insert(
        2,
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="black"/></marker></defs>',
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "Usage: plot_figure8.py <Figure 8 raw> <Figure 10 raw> <J111 package directory>"
        )

    raw_path, figure10_raw_path, package_dir = map(Path, sys.argv[1:])
    data_dir = package_dir / "sim" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    variables, rows = read_ascii_raw(raw_path)
    validate_default_model(variables, rows)
    curves = [
        resistance_curve(variables, rows, source)
        for _, source in CURVES
    ]
    if any(not curve for curve in curves):
        raise ValueError("LTspice output did not contain usable points for every Figure 8 curve")
    figure8_csv = data_dir / "figure8.csv"
    figure8_svg = package_dir / "figure8.svg"
    write_csv(figure8_csv, curves)
    write_svg(figure8_svg, curves)
    figure10 = figure10_data(figure10_raw_path)
    figure10_csv = data_dir / "figure10.csv"
    figure10_svg = package_dir / "figure10.svg"
    write_figure10_csv(figure10_csv, figure10)
    write_figure10_svg(figure10_svg, figure10)
    print(f"Wrote {figure8_csv}, {figure8_svg}, {figure10_csv}, and {figure10_svg}")


if __name__ == "__main__":
    main()
