import csv
import math
import re
import sys
from pathlib import Path


INPUT_CURRENTS = [10e-6, 20e-6, 50e-6, 100e-6]
OUTPUTS = ["i(vout1)", "i(vout2)", "i(vout3)", "i(vout4)"]
COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]
CONTROL_SCALE = 33e-3 * 20 / math.log(10)
GAIN_MIN = 1e-5
GAIN_MAX = 10
VC_MIN = -3
VC_MAX = 3


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

    if not rows or "v(ctrl)" not in variables:
        raise ValueError(f"No sweep data or V(CTRL) variable found in {path}")
    if any(len(point) != len(variables) for point in rows):
        raise ValueError(f"Unexpected ASCII raw data row width in {path}")
    for output in OUTPUTS:
        if output not in variables:
            raise ValueError(f"LTspice output is missing {output}")
    return variables, rows


def collect_data(variables, rows):
    control_index = variables["v(ctrl)"]
    output_indices = [variables[output] for output in OUTPUTS]
    data = []
    checked_points = set()
    for row in rows:
        control = row[control_index]
        measured_gains = []
        for input_current, output_index in zip(INPUT_CURRENTS, output_indices):
            output_current = row[output_index]
            expected_gain = min(max(math.exp(-control / CONTROL_SCALE), GAIN_MIN), GAIN_MAX)
            expected = input_current * expected_gain
            if output_current <= 0:
                raise ValueError(
                    f"Output current must be positive for {input_current:g} A input at VC={control:g} V"
                )
            relative_error = abs(output_current - expected) / expected
            if relative_error > 1e-6:
                raise ValueError(
                    f"Exponential law mismatch at VC={control:g} V: "
                    f"measured {output_current:g} A, expected {expected:g} A"
                )
            measured_gains.append(output_current / input_current)
            data.append((control, input_current, output_current))
        if max(measured_gains) - min(measured_gains) > 1e-6 * max(measured_gains):
            raise ValueError(f"VCA output is not proportional to input current at VC={control:g} V")
        if round(control, 9) in (-1.0, 0.0, 1.0, 3.0):
            gain_db = 20 * math.log10(measured_gains[0])
            expected_db = min(max(-control / 0.033, -100), 20)
            if abs(gain_db - expected_db) > 1e-4:
                raise ValueError(
                    f"Datasheet gain-range check failed at VC={control:g} V: "
                    f"{gain_db:.3f} dB vs {expected_db:.3f} dB"
                )
            checked_points.add(control)
    if checked_points != {-1.0, 0.0, 1.0, 3.0}:
        raise ValueError(f"LTspice sweep is missing datasheet check points: {checked_points}")
    gain_at_minus_3 = next(
        row[output_indices[0]] / INPUT_CURRENTS[0]
        for row in rows
        if abs(row[control_index] + 3) < 1e-9
    )
    gain_at_plus_3 = next(
        row[output_indices[0]] / INPUT_CURRENTS[0]
        for row in rows
        if abs(row[control_index] - 3) < 1e-9
    )
    gain_at_minus_3_db = 20 * math.log10(gain_at_minus_3)
    attenuation_at_plus_3_db = -20 * math.log10(gain_at_plus_3)
    if not 17 <= gain_at_minus_3_db <= 23:
        raise ValueError(f"VC=-3 V gain is outside the AS2164 +17 to +23 dB limits: {gain_at_minus_3_db:.3f} dB")
    if not 90 <= attenuation_at_plus_3_db <= 110:
        raise ValueError(
            f"VC=+3 V attenuation is outside the AS2164 90 to 110 dB range: "
            f"{attenuation_at_plus_3_db:.3f} dB"
        )
    print(
        "Datasheet checks passed: -33 mV/dB slope, unity gain at 0 V, "
        f"VC=-3 V gain {gain_at_minus_3_db:.2f} dB (SSM2164 max +20 dB; "
        "AS2164 +17 to +23 dB), and "
        f"VC=+3 V attenuation {attenuation_at_plus_3_db:.2f} dB "
        "(AS2164 90 to 110 dB)."
    )
    return data


def write_csv(path, data):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["VC (V)", "IIN (A)", "IOUT (A)", "Gain"])
        writer.writerows(
            (f"{control:.6f}", f"{input_current:.9g}", f"{output_current:.9g}",
             f"{output_current / input_current:.9g}")
            for control, input_current, output_current in data
        )


def write_svg(path, rows):
    width, height = 900, 600
    left, top, right, bottom = 110, 55, 35, 85
    plot_width = width - left - right
    plot_height = height - top - bottom
    x_min, x_max = VC_MIN, VC_MAX
    y_min, y_max = math.log10(1e-10), math.log10(1e-3)

    def x_pixel(value):
        return left + (value - x_min) / (x_max - x_min) * plot_width

    def y_pixel(value):
        return top + (y_max - math.log10(value)) / (y_max - y_min) * plot_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="450" y="28" text-anchor="middle" font-family="Arial" font-size="19" font-weight="bold">SSM2164 / AS2164: Exponential Current VCA Transfer</text>',
    ]
    for tick in range(-3, 4):
        control = float(tick)
        x = x_pixel(control)
        parts.extend(
            [
                f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}" stroke="#d0d0d0"/>',
                f'<text x="{x:.2f}" y="{top + plot_height + 22}" text-anchor="middle" font-family="Arial" font-size="12">{control:.0f}</text>',
            ]
        )
    current_ticks = [
        (1e-10, "0.1 nA"),
        (1e-9, "1 nA"),
        (1e-8, "10 nA"),
        (1e-7, "100 nA"),
        (1e-6, "1 uA"),
        (1e-5, "10 uA"),
        (1e-4, "100 uA"),
        (1e-3, "1 mA"),
    ]
    for current, label in current_ticks:
        y = y_pixel(current)
        parts.extend(
            [
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#d0d0d0"/>',
                f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial" font-size="12">{label}</text>',
            ]
        )

    parts.extend(
        [
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="black" stroke-width="2"/>',
            f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="black" stroke-width="2"/>',
            f'<text x="{left + plot_width / 2:.2f}" y="{height - 28}" text-anchor="middle" font-family="Arial" font-size="16">Control voltage VC (V)</text>',
            f'<text x="24" y="{top + plot_height / 2:.2f}" transform="rotate(-90 24 {top + plot_height / 2:.2f})" text-anchor="middle" font-family="Arial" font-size="16">Output current IOUT (log scale)</text>',
        ]
    )

    for index, (input_current, color) in enumerate(zip(INPUT_CURRENTS, COLORS)):
        points = [(control, current) for control, channel, current in rows if channel == input_current]
        path_data = " ".join(
            ("M" if point_index == 0 else "L")
            + f"{x_pixel(control):.2f},{y_pixel(current):.2f}"
            for point_index, (control, current) in enumerate(points)
        )
        parts.append(f'<path d="{path_data}" fill="none" stroke="{color}" stroke-width="3"/>')
        legend_y = top + 20 + index * 22
        parts.extend(
            [
                f'<line x1="{left + 18}" y1="{legend_y}" x2="{left + 42}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>',
                f'<text x="{left + 48}" y="{legend_y + 5}" font-family="Arial" font-size="12">IIN = {input_current * 1e6:g} uA</text>',
            ]
        )

    max_gain_vc = -0.033 * 20
    parts.extend(
        [
            f'<line x1="{x_pixel(max_gain_vc):.2f}" y1="{top}" x2="{x_pixel(max_gain_vc):.2f}" y2="{top + plot_height}" stroke="#555" stroke-dasharray="5,4"/>',
            f'<text x="{x_pixel(max_gain_vc) + 6:.2f}" y="{top + 14}" font-family="Arial" font-size="11">SSM2164 +20 dB limit; AS2164 +22 dB typ.</text>',
            '<text x="450" y="580" text-anchor="middle" font-family="Arial" font-size="12">VC = +/-3 V; -33 mV/dB typical. Model clamps at +20/-100 dB; +/-3 V yields +20/-90.9 dB.</text>',
        ]
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: plot_transfer.py <LTspice ASCII raw> <2164 package directory>")
    raw_path, package_dir = map(Path, sys.argv[1:])
    variables, raw_rows = read_ascii_raw(raw_path)
    data = collect_data(variables, raw_rows)
    data_dir = package_dir / "sim" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "vca_transfer.csv"
    svg_path = package_dir / "vca_transfer.svg"
    write_csv(csv_path, data)
    write_svg(svg_path, data)
    print(f"Verified exponential gain law and wrote {csv_path} and {svg_path}")


if __name__ == "__main__":
    main()
