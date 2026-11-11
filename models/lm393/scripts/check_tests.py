import re
import sys
from pathlib import Path


def parse_value(value):
    if "," in value:
        real, imaginary = value.split(",", 1)
        return complex(float(real), float(imaginary))
    return complex(value.replace("i", "j"))


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
            row = [parse_value(value) for value in fields[1:]]
        elif row is not None:
            row.extend(parse_value(value) for value in fields)
    if row is not None:
        rows.append(row)
    if not rows or any(len(point) != len(variables) for point in rows):
        raise ValueError(f"Missing or malformed LTspice points in {path}")
    return variables, rows


def check_dc(path):
    variables, rows = read_ascii_raw(path)
    input_index = variables["v(inp)"]
    output_index = variables["v(out)"]
    points = [(row[input_index].real, row[output_index].real) for row in rows]
    low = min(points, key=lambda point: abs(point[0] - 1.0))
    high = min(points, key=lambda point: abs(point[0] - 3.0))
    if not 0 <= low[1] <= 0.5:
        raise ValueError(f"Open-collector output did not pull low below threshold: {low[1]:.3f} V")
    if high[1] < 4.5:
        raise ValueError(f"Comparator output did not release high above threshold: {high[1]:.3f} V")
    transition = next(
        (input_voltage for input_voltage, voltage in points if input_voltage > 2.5 and voltage > 2.5),
        None,
    )
    if transition is None or abs(transition - 2.5) > 0.03:
        raise ValueError(f"Comparator switching threshold is {transition}, expected near 2.5 V")
    print(f"DC check: VOUT={low[1]:.2f} V at VIN=1 V and {high[1]:.2f} V at VIN=3 V")


def crossing_time(points, threshold, rising):
    for (time1, value1), (time2, value2) in zip(points, points[1:]):
        crossed = value1 < threshold <= value2 if rising else value1 > threshold >= value2
        if crossed and value2 != value1:
            fraction = (threshold - value1) / (value2 - value1)
            return time1 + fraction * (time2 - time1)
    raise ValueError(f"Signal did not cross {threshold} V ({'rising' if rising else 'falling'})")


def check_transient(path):
    variables, rows = read_ascii_raw(path)
    time_index = variables["time"]
    input_index = variables["v(inp)"]
    output_index = variables["v(out)"]
    inputs = [(row[time_index].real, row[input_index].real) for row in rows]
    outputs = [(row[time_index].real, row[output_index].real) for row in rows]
    input_crossing = crossing_time(inputs, 2.5, True)
    output_crossing = crossing_time(outputs, 2.5, True)
    delay_us = (output_crossing - input_crossing) * 1e6
    if not 0.7 <= delay_us <= 2.0:
        raise ValueError(f"Comparator propagation delay is {delay_us:.3f} us, expected about 1.3 us")
    print(f"Transient check: input-to-output propagation delay={delay_us:.2f} us")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_tests.py <LTspice simulation output directory>")
    directory = Path(sys.argv[1])
    check_dc(directory / "lm393_dc.raw")
    check_transient(directory / "lm393_transient.raw")


if __name__ == "__main__":
    main()
