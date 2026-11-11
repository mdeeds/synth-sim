import csv
import re
import sys
from pathlib import Path


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

    required = {"time", "v(in)", "v(out)", "v(iout1)", "i(vimon)", "i(vomon)"}
    missing = required - variables.keys()
    if missing:
        raise ValueError(f"LTspice raw data is missing variables: {', '.join(sorted(missing))}")

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

    if not rows or any(len(point) != len(variables) for point in rows):
        raise ValueError(f"Missing or malformed LTspice data points in {path}")
    return variables, rows


def write_csv(path, variables, rows):
    columns = ["time", "v(in)", "v(out)", "i(vimon)", "i(vomon)", "v(iout1)"]
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow([
            "Time (s)", "IN (V)", "OUT (V)", "Current into 2164 (A)",
            "Current out of 2164 (A)", "2164 IOUT1 pin (V)",
        ])
        for row in rows:
            writer.writerow([f"{row[variables[column]]:.12g}" for column in columns])


def write_svg(path, variables, rows):
    width, height = 1200, 900
    left, right = 105, 35
    plot_width = width - left - right
    voltage_top, voltage_height = 100, 220
    current_top, current_height = 390, 200
    pin_top, pin_height = 660, 150
    time_index = variables["time"]
    signals = {
        "IN": (variables["v(in)"], "#1f77b4"),
        "OUT": (variables["v(out)"], "#d62728"),
        "IIN": (variables["i(vimon)"], "#2ca02c"),
        "IOUT": (variables["i(vomon)"], "#9467bd"),
        "PIN": (variables["v(iout1)"], "#ff7f0e"),
    }
    times = [row[time_index] for row in rows]
    time_min, time_max = min(times), max(times)
    if time_max <= time_min:
        raise ValueError("Simulation data has no positive time range")

    def x_pixel(time):
        return left + (time - time_min) / (time_max - time_min) * plot_width

    voltage_min, voltage_max = -15.0, 15.0
    current_values = [
        row[variables[name]]
        for row in rows
        for name in ("i(vimon)", "i(vomon)")
    ]
    current_limit = max(abs(value) for value in current_values) * 1.08
    if current_limit == 0:
        current_limit = 1e-12

    def voltage_y(value):
        return voltage_top + (voltage_max - value) / (voltage_max - voltage_min) * voltage_height

    def current_y(value):
        return current_top + (current_limit - value) / (2 * current_limit) * current_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="600" y="34" text-anchor="middle" font-family="Arial" font-size="21" font-weight="bold">SSM2164 / TL072 Integrator Transient</text>',
        '<text x="600" y="60" text-anchor="middle" font-family="Arial" font-size="14">1 kHz square input, +/-5 V; VC = +0.774 V</text>',
    ]

    def draw_axes(top, height_, y_ticks, y_map, label, formatter):
        parts.append(f'<text x="{left + plot_width / 2}" y="{top - 20}" text-anchor="middle" font-family="Arial" font-size="16">{label}</text>')
        for tick in y_ticks:
            y = y_map(tick)
            parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#dddddd"/>')
            parts.append(f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial" font-size="12">{formatter(tick)}</text>')
        for tick_ms in range(0, 3):
            time = tick_ms / 1000
            x = x_pixel(time)
            parts.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + height_}" stroke="#e5e5e5"/>')
            parts.append(f'<text x="{x:.2f}" y="{top + height_ + 20}" text-anchor="middle" font-family="Arial" font-size="12">{tick_ms}</text>')
        parts.extend([
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + height_}" stroke="black"/>',
            f'<line x1="{left}" y1="{top + height_}" x2="{left + plot_width}" y2="{top + height_}" stroke="black"/>',
        ])

    draw_axes(voltage_top, voltage_height, [-15, -10, -5, 0, 5, 10, 15], voltage_y, "Voltage", lambda value: f"{value:g} V")
    draw_axes(
        current_top,
        current_height,
        [-current_limit, -current_limit / 2, 0, current_limit / 2, current_limit],
        current_y,
        "Current at 2164 pins",
        lambda value: f"{value * 1e6:.3g} uA",
    )
    draw_axes(
        pin_top,
        pin_height,
        [-0.6, -0.3, 0, 0.3, 0.6],
        lambda value: pin_top + (0.6 - value) / 1.2 * pin_height,
        "2164 IOUT1 pin voltage relative to ground",
        lambda value: f"{value:.1f} V",
    )

    for signal, label, color, index, mapper, top in [
        ("IN", "IN", signals["IN"][1], signals["IN"][0], voltage_y, voltage_top),
        ("OUT", "OUT", signals["OUT"][1], signals["OUT"][0], voltage_y, voltage_top),
        ("IIN", "Into 2164 IIN1", signals["IIN"][1], signals["IIN"][0], current_y, current_top),
        ("IOUT", "Out of 2164 IOUT1", signals["IOUT"][1], signals["IOUT"][0], current_y, current_top),
        ("PIN", "2164 IOUT1 pin voltage", signals["PIN"][1], signals["PIN"][0],
         lambda value: pin_top + (0.6 - value) / 1.2 * pin_height, pin_top),
    ]:
        points = " ".join(
            ("M" if point_index == 0 else "L")
            + f"{x_pixel(row[time_index]):.2f},{mapper(row[index]):.2f}"
            for point_index, row in enumerate(rows)
        )
        parts.append(f'<path d="{points}" fill="none" stroke="{color}" stroke-width="1.5"/>')
        legend_y = top + 18
        legend_x = left + 18 + (0 if signal in ("IN", "IIN") else 140)
        parts.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 24}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<text x="{legend_x + 30}" y="{legend_y + 4}" font-family="Arial" font-size="12">{label}</text>')

    parts.extend([
        f'<text x="{left + plot_width / 2}" y="850" text-anchor="middle" font-family="Arial" font-size="14">Time (ms)</text>',
        '<text x="600" y="880" text-anchor="middle" font-family="Arial" font-size="11">Positive input current flows into IIN1; positive output current flows from IOUT1 toward the TL072 summing node. Output compliance is clamped by the behavioral model.</text>',
        "</svg>",
    ])
    path.write_text("\n".join(parts), encoding="utf-8")


def verify_waveform(variables, rows):
    time_index = variables["time"]
    output_index = variables["v(out)"]
    pin_index = variables["v(iout1)"]
    second_cycle = [row for row in rows if 1e-3 <= row[time_index] <= 2e-3]
    if not second_cycle:
        raise ValueError("Simulation data does not include the expected second cycle")

    output_values = [row[output_index] for row in second_cycle]
    output_min, output_max = min(output_values), max(output_values)
    if not -5.2 <= output_min <= -4.8 or not 4.8 <= output_max <= 5.2:
        raise ValueError(
            f"OUT did not reach approximately +/-5 V in the second cycle: "
            f"{output_min:.3f} V to {output_max:.3f} V"
        )

    pin_limit = max(abs(row[pin_index]) for row in rows)
    if pin_limit > 0.6:
        raise ValueError(f"2164 IOUT1 pin exceeded its +/-0.6 V compliance limit: {pin_limit:.3f} V")
    print(
        f"Waveform check: OUT={output_min:.3f} V to {output_max:.3f} V; "
        f"2164 IOUT1 pin peak={pin_limit:.4f} V"
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: plot_integrator.py <LTspice ASCII raw> <output directory>")
    raw_path, output_dir = Path(sys.argv[1]), Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)
    variables, rows = read_ascii_raw(raw_path)
    verify_waveform(variables, rows)
    write_csv(output_dir / "integrator_1khz.csv", variables, rows)
    write_svg(output_dir / "integrator_1khz.svg", variables, rows)
    print(f"Wrote {output_dir / 'integrator_1khz.svg'} and {output_dir / 'integrator_1khz.csv'}")


if __name__ == "__main__":
    main()
