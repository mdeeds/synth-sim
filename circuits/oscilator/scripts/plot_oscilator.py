import csv
import re
import sys
from pathlib import Path


SIGNALS = [
    ("v(cap)", "CAP / integrator OUT", "#d62728", "voltage"),
    ("v(in)", "IN drive node", "#1f77b4", "voltage"),
    ("v(wiper)", "R_TRIM wiper", "#ff7f0e", "voltage"),
    ("v(hyst)", "Schmitt output", "#2ca02c", "logic"),
    ("v(sq)", "SQ", "#9467bd", "logic"),
    ("v(vth)", "Schmitt threshold", "#ff7f0e", "voltage"),
    ("i(vimon)", "2164 IIN1 current", "#17becf", "current"),
    ("i(vomon)", "2164 IOUT1 current", "#8c564b", "current"),
    ("v(iout1)", "2164 IOUT1 pin", "#e377c2", "pin"),
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

    required = {"time", *(signal[0] for signal in SIGNALS)}
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


def write_svg(path, variables, rows):
    width, height = 1200, 1000
    left, right = 110, 35
    plot_width = width - left - right
    panel_top = [105, 315, 525, 735]
    panel_height = 155
    time_index = variables["time"]
    times = [row[time_index] for row in rows]
    time_min, time_max = min(times), max(times)
    if time_max <= time_min:
        raise ValueError("Simulation data has no positive time range")

    def x_pixel(time):
        return left + (time - time_min) / (time_max - time_min) * plot_width

    groups = [
        ("Integrator and trim input voltage", ["v(cap)", "v(in)", "v(wiper)"], -15, 15, "V"),
        ("Comparator outputs and threshold", ["v(hyst)", "v(sq)", "v(vth)"], -16, 16, "V"),
        ("2164 current", ["i(vimon)", "i(vomon)"], None, None, "A"),
        ("2164 IOUT1 compliance pin", ["v(iout1)"], -0.6, 0.6, "V"),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="600" y="34" text-anchor="middle" font-family="Arial" font-size="21" font-weight="bold">Asymmetric SSM2164 / TL072 Oscillator</text>',
        '<text x="600" y="60" text-anchor="middle" font-family="Arial" font-size="14">LM393 Schmitt feedback; CV = 0.774 V; R_TRIM position = 30% from SQ</text>',
    ]

    signal_by_name = {item[0]: item for item in SIGNALS}
    for group_index, (title, names, y_min, y_max, unit) in enumerate(groups):
        top = panel_top[group_index]
        if y_min is None:
            values = [row[variables[name]] for row in rows for name in names]
            extent = max(abs(value) for value in values) * 1.08
            extent = extent or 1e-12
            y_min, y_max = -extent, extent

        def y_pixel(value):
            return top + (y_max - value) / (y_max - y_min) * panel_height

        parts.append(f'<text x="{left + plot_width / 2}" y="{top - 14}" text-anchor="middle" font-family="Arial" font-size="15">{title}</text>')
        tick_count = 4
        for tick_index in range(tick_count + 1):
            value = y_min + (y_max - y_min) * tick_index / tick_count
            y = y_pixel(value)
            label = f"{value * 1e6:.3g} uA" if unit == "A" else f"{value:.3g} {unit}"
            parts.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#dddddd"/>')
            parts.append(f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial" font-size="11">{label}</text>')
        for tick_index in range(6):
            time = time_min + (time_max - time_min) * tick_index / 5
            x = x_pixel(time)
            parts.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + panel_height}" stroke="#eeeeee"/>')
            parts.append(f'<text x="{x:.2f}" y="{top + panel_height + 17}" text-anchor="middle" font-family="Arial" font-size="10">{time * 1e3:.2f}</text>')
        parts.extend([
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + panel_height}" stroke="black"/>',
            f'<line x1="{left}" y1="{top + panel_height}" x2="{left + plot_width}" y2="{top + panel_height}" stroke="black"/>',
        ])

        for legend_index, name in enumerate(names):
            _, label, color, _ = signal_by_name[name]
            index = variables[name]
            points = " ".join(
                ("M" if point_index == 0 else "L")
                + f"{x_pixel(row[time_index]):.2f},{y_pixel(row[index]):.2f}"
                for point_index, row in enumerate(rows)
            )
            parts.append(f'<path d="{points}" fill="none" stroke="{color}" stroke-width="1.5"/>')
            legend_x = left + 14 + legend_index * 220
            legend_y = top + 14
            parts.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 22}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
            parts.append(f'<text x="{legend_x + 28}" y="{legend_y + 4}" font-family="Arial" font-size="11">{label}</text>')

    parts.extend([
        f'<text x="{left + plot_width / 2}" y="965" text-anchor="middle" font-family="Arial" font-size="13">Time (ms)</text>',
        "</svg>",
    ])
    path.write_text("\n".join(parts), encoding="utf-8")


def verify_oscillation(variables, rows):
    time_index = variables["time"]
    cap_index = variables["v(cap)"]
    hyst_index = variables["v(hyst)"]
    pin_index = variables["v(iout1)"]
    crossings = []
    for previous, current in zip(rows, rows[1:]):
        previous_hyst = previous[hyst_index]
        current_hyst = current[hyst_index]
        if (previous_hyst < 0 <= current_hyst) or (previous_hyst > 0 >= current_hyst):
            fraction = -previous_hyst / (current_hyst - previous_hyst)
            time = previous[time_index] + fraction * (current[time_index] - previous[time_index])
            cap = previous[cap_index] + fraction * (current[cap_index] - previous[cap_index])
            if time >= 0.005:
                crossings.append((time, cap))

    intervals = [
        crossings[index + 1][0] - crossings[index][0]
        for index in range(len(crossings) - 1)
    ]
    periods = [
        crossings[index + 2][0] - crossings[index][0]
        for index in range(len(crossings) - 2)
    ]
    if len(periods) < 3 or not intervals:
        raise ValueError("Oscillator did not produce enough steady-state comparator transitions")

    average_period = sum(periods) / len(periods)
    half_periods = sorted(intervals)
    slow_ramp, fast_ramp = half_periods[-1], half_periods[0]
    asymmetry = slow_ramp / fast_ramp
    cap_at_switch = [cap for _, cap in crossings]
    switch_low, switch_high = min(cap_at_switch), max(cap_at_switch)
    peak_pin_voltage = max(abs(row[pin_index]) for row in rows)

    if not 4.5e-3 <= average_period <= 7e-3:
        raise ValueError(f"Oscillator period {average_period * 1e3:.3f} ms is outside the expected range")
    if asymmetry < 5:
        raise ValueError(f"Ramp asymmetry is only {asymmetry:.2f}:1, not sawtooth-like")
    if not -8.5 <= switch_low <= -6.5 or not 6.5 <= switch_high <= 8.5:
        raise ValueError(
            f"Schmitt thresholds are not near +/-7.5 V: {switch_low:.2f} V, {switch_high:.2f} V"
        )
    if peak_pin_voltage > 0.6:
        raise ValueError(f"2164 IOUT1 exceeded its +/-0.6 V compliance limit: {peak_pin_voltage:.3f} V")

    print(
        f"Oscillator check: period={average_period * 1e3:.3f} ms, "
        f"slow/fast ramp={asymmetry:.1f}:1, switching levels="
        f"{switch_low:.2f} V to {switch_high:.2f} V, "
        f"2164 IOUT1 pin peak={peak_pin_voltage:.4f} V"
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: plot_oscilator.py <LTspice ASCII raw> <output directory>")
    raw_path, output_dir = Path(sys.argv[1]), Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)
    variables, rows = read_ascii_raw(raw_path)
    verify_oscillation(variables, rows)
    write_csv(output_dir / "oscilator.csv", variables, rows)
    write_svg(output_dir / "oscilator.svg", variables, rows)
    print(f"Wrote {output_dir / 'oscilator.svg'} and {output_dir / 'oscilator.csv'}")


if __name__ == "__main__":
    main()
