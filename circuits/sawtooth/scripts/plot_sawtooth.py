import csv
import html
import math
import re
import sys
from pathlib import Path


SIGNALS = [
    ("v(cap)", "CAP / integrator output", "#d62728", "V"),
    ("v(in)", "IN", "#1f77b4", "V"),
    ("v(sqdiv)", "Scaled comparator square", "#9467bd", "V"),
    ("v(mixout)", "TL072 mixed output", "#2ca02c", "V"),
    ("v(mixw)", "RV1 wiper", "#ff7f0e", "V"),
    ("v(hyst)", "LM393 HYST", "#2ca02c", "V"),
    ("v(reset)", "LM393 RESET / J111 drive", "#9467bd", "V"),
    ("v(vth)", "Schmitt threshold", "#ff7f0e", "V"),
    ("i(vimon)", "2164 IIN1", "#17becf", "A"),
    ("i(vomon)", "2164 IOUT1", "#8c564b", "A"),
    ("i(vqmon)", "J111 drain current", "#e377c2", "A"),
    ("v(gate)", "J111 gate", "#7f7f7f", "V"),
]


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

    required = {"time", "v(sqdiv)", *(signal[0] for signal in SIGNALS)}
    missing = required - variables.keys()
    if missing:
        raise ValueError(f"LTspice raw file is missing variables: {', '.join(sorted(missing))}")

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
    columns = ["time"] + [signal[0] for signal in SIGNALS]
    headers = ["Time (s)"] + [signal[1] for signal in SIGNALS]
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([f"{row[variables[column]]:.12g}" for column in columns])


def measure(variables, rows):
    time_i = variables["time"]
    cap_i = variables["v(cap)"]
    hyst_i = variables["v(hyst)"]
    steady = [row for row in rows if row[time_i] >= 0.002]
    if len(steady) < 10:
        raise ValueError("Simulation is too short to measure steady-state oscillation")

    crossings = []
    for previous, current in zip(steady, steady[1:]):
        a, b = previous[hyst_i], current[hyst_i]
        if (a < 0 <= b) or (a > 0 >= b):
            fraction = -a / (b - a)
            crossing_time = previous[time_i] + fraction * (current[time_i] - previous[time_i])
            crossing_cap = previous[cap_i] + fraction * (current[cap_i] - previous[cap_i])
            crossings.append((crossing_time, crossing_cap, b > a))

    rising = [item[0] for item in crossings if item[2]]
    periods = [b - a for a, b in zip(rising, rising[1:])]
    if len(periods) < 3:
        raise ValueError("Insufficient steady-state comparator transitions for measurement")

    period = sum(periods) / len(periods)
    cap_min = min(row[cap_i] for row in steady)
    cap_max = max(row[cap_i] for row in steady)
    gate_i = variables["v(gate)"]
    gate_min = min(row[gate_i] for row in steady)
    gate_max = max(row[gate_i] for row in steady)
    match = re.search(r"(?im)^\s*\.param\s+MIX\s*=\s*([0-9.e+-]+)", (Path(__file__).parents[1] / "sawtooth.cir").read_text(encoding="utf-8"))
    if not match:
        raise ValueError("Could not read the MIX parameter from sawtooth.cir")
    mix = float(match.group(1))
    mix_errors = [
        abs(
            row[variables["v(mixout)"]]
            - (
                (1 - mix) * row[cap_i]
                + mix * row[variables["v(sqdiv)"]]
            )
        )
        for row in steady
    ]
    mix_error = max(mix_errors)
    mix_error_p99 = sorted(mix_errors)[int(0.99 * (len(mix_errors) - 1))]

    if not 0.5e-3 <= period <= 0.9e-3:
        raise ValueError(f"Unexpected sawtooth period: {period * 1e3:.3f} ms")
    if not -3.2 <= cap_min <= -2.0 or not -0.5 <= cap_max <= 0.2:
        raise ValueError(f"Unexpected steady-state CAP range: {cap_min:.3f} to {cap_max:.3f} V")
    if not gate_min < -10 or not gate_max > 0.3:
        raise ValueError(f"J111 gate is not switching between off and reset levels: {gate_min:.2f} to {gate_max:.2f} V")
    if max(abs(row[variables["v(iout1)"]]) for row in steady) > 0.6:
        raise ValueError("The SSM2164 IOUT1 pin exceeded its +/-0.6 V compliance limit")
    if mix_error_p99 > 0.15 or mix_error > 8:
        raise ValueError(
            "TL072 mix output does not follow the RV1 crossfade: "
            f"99th percentile error={mix_error_p99:.3f} V, peak edge error={mix_error:.3f} V"
        )

    return period, cap_min, cap_max, len(periods), gate_min, gate_max, mix, mix_error_p99, mix_error


def write_svg(path, variables, rows, measurements):
    width, height = 1200, 980
    left, right = 110, 35
    plot_width = width - left - right
    panel_tops = [110, 320, 530, 740]
    panel_height = 155
    time_i = variables["time"]
    stride = max(1, math.ceil(len(rows) / 6000))
    sampled = rows[::stride]
    if sampled[-1] is not rows[-1]:
        sampled.append(rows[-1])
    time_min = min(row[time_i] for row in sampled) * 1e3
    time_max = max(row[time_i] for row in sampled) * 1e3
    if time_max <= time_min:
        raise ValueError("Simulation data has no positive time range")

    groups = [
        ("Sawtooth and comparator square-wave crossfade", ["v(cap)", "v(sqdiv)", "v(mixout)"], "Voltage (V)", -6, 6, 1),
        ("LM393 control and J111 gate", ["v(hyst)", "v(reset)", "v(vth)", "v(gate)"], "Voltage (V)", -16, 16, 1),
        ("2164 and J111 currents", ["i(vimon)", "i(vomon)", "i(vqmon)"], "Current (uA)", None, None, 1e6),
        ("Potentiometer wiper and buffered output", ["v(mixw)", "v(mixout)"], "Voltage (V)", -6, 6, 1),
    ]
    signal_info = {name: (label, color, unit) for name, label, color, unit in SIGNALS}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="600" y="34" text-anchor="middle" font-family="Arial" font-size="21" font-weight="bold">Fixed-Input SSM2164 Sawtooth Oscillator with J111 Reset</text>',
    ]
    period, cap_min, cap_max, _, _, _, mix, _, _ = measurements
    subtitle = (
        f"LTspice macromodel | CV = 0.774 V | period = {period * 1e3:.3f} ms | "
        f"CAP = {cap_min:.2f} to {cap_max:.2f} V | RV1 = {mix:.0%} toward square"
    )
    parts.append(
        f'<text x="600" y="60" text-anchor="middle" font-family="Arial" font-size="13">{html.escape(subtitle)}</text>'
    )

    for panel_index, (title, names, ylabel, y_min, y_max, scale) in enumerate(groups):
        top = panel_tops[panel_index]
        if y_min is None:
            extent = max(
                abs(row[variables[name]] * scale)
                for row in rows
                for name in names
            ) * 1.1
            extent = extent or 1.0
            y_min, y_max = -extent, extent

        def x_pixel(time_ms):
            return left + (time_ms - time_min) / (time_max - time_min) * plot_width

        def y_pixel(value):
            return top + (y_max - value) / (y_max - y_min) * panel_height

        parts.append(
            f'<text x="{left + plot_width / 2:.1f}" y="{top - 15}" text-anchor="middle" font-family="Arial" font-size="15">{html.escape(title)}</text>'
        )
        for tick in range(5):
            value = y_min + (y_max - y_min) * tick / 4
            y = y_pixel(value)
            parts.append(
                f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#dddddd"/>'
            )
            parts.append(
                f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial" font-size="11">{value:.3g}</text>'
            )
        for tick in range(6):
            time_ms = time_min + (time_max - time_min) * tick / 5
            x = x_pixel(time_ms)
            parts.append(
                f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + panel_height}" stroke="#eeeeee"/>'
            )
            parts.append(
                f'<text x="{x:.2f}" y="{top + panel_height + 16}" text-anchor="middle" font-family="Arial" font-size="10">{time_ms:.2f}</text>'
            )
        parts.extend(
            [
                f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + panel_height}" stroke="black"/>',
                f'<line x1="{left}" y1="{top + panel_height}" x2="{left + plot_width}" y2="{top + panel_height}" stroke="black"/>',
            ]
        )

        for legend_index, name in enumerate(names):
            label, color, _ = signal_info[name]
            points = " ".join(
                ("M" if point_index == 0 else "L")
                + f"{x_pixel(row[time_i] * 1e3):.2f},{y_pixel(row[variables[name]] * scale):.2f}"
                for point_index, row in enumerate(sampled)
            )
            parts.append(f'<path d="{points}" fill="none" stroke="{color}" stroke-width="1.4"/>')
            legend_x = left + 14 + legend_index * 220
            legend_y = top + 14
            parts.append(
                f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 22}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>'
            )
            parts.append(
                f'<text x="{legend_x + 28}" y="{legend_y + 4}" font-family="Arial" font-size="11">{html.escape(label)}</text>'
            )
        parts.append(
            f'<text transform="translate(24 {top + panel_height / 2}) rotate(-90)" text-anchor="middle" font-family="Arial" font-size="12">{html.escape(ylabel)}</text>'
        )

    parts.extend(
        [
            f'<text x="{left + plot_width / 2}" y="962" text-anchor="middle" font-family="Arial" font-size="13">Time (ms)</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: plot_sawtooth.py <LTspice ASCII raw> <output directory>")
    raw_path, output_dir = Path(sys.argv[1]), Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)
    variables, rows = read_ascii_raw(raw_path)
    measurements = measure(variables, rows)
    write_csv(output_dir / "sawtooth.csv", variables, rows)
    write_svg(output_dir / "sawtooth.svg", variables, rows, measurements)
    period, cap_min, cap_max, cycles, gate_min, gate_max, mix, mix_error_p99, mix_error = measurements
    print(
        f"Sawtooth check: period={period * 1e3:.3f} ms, "
        f"CAP={cap_min:.3f}..{cap_max:.3f} V, cycles={cycles}, "
        f"J111 gate={gate_min:.2f}..{gate_max:.2f} V, "
        f"RV1={mix:.0%} square, tracking p99={mix_error_p99:.3g} V, "
        f"peak edge error={mix_error:.3g} V"
    )
    print(f"Wrote {output_dir / 'sawtooth.svg'} and {output_dir / 'sawtooth.csv'}")


if __name__ == "__main__":
    main()
