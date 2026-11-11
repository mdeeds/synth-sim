import math
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


def check_ac(path):
    variables, rows = read_ascii_raw(path)
    frequency_index = variables.get("frequency", 0)
    output_index = variables["v(out)"]
    response = [(float(row[frequency_index].real), abs(row[output_index])) for row in rows]
    low_frequency_gain = response[0][1]
    if not 0.95 <= low_frequency_gain <= 1.05:
        raise ValueError(f"TL072 follower low-frequency gain is {low_frequency_gain:.4g}, expected near 1")
    target = low_frequency_gain / math.sqrt(2)
    bandwidth = next(
        (frequency for frequency, gain in response if gain <= target),
        None,
    )
    if bandwidth is None or not 3.5e6 <= bandwidth <= 7.5e6:
        raise ValueError(f"TL072 follower -3 dB bandwidth is {bandwidth}, expected about 5.25 MHz")
    print(f"AC check: low-frequency gain={low_frequency_gain:.4f}, -3 dB bandwidth={bandwidth:.3g} Hz")


def check_transient(path):
    variables, rows = read_ascii_raw(path)
    time_index = variables.get("time", 0)
    output_index = variables["v(out)"]
    points = [(row[time_index].real, row[output_index].real) for row in rows]
    rising = [
        (t, value)
        for t, value in points
        if 1.05e-6 <= t <= 1.85e-6 and 0.5 <= value <= 9.5
    ]
    if len(rising) < 3:
        raise ValueError("Transient output did not contain enough samples of the large-signal rising edge")
    slopes = [
        (value2 - value1) / (time2 - time1) / 1e6
        for (time1, value1), (time2, value2) in zip(rising, rising[1:])
        if time2 > time1
    ]
    slew = max(slopes)
    if not 10 <= slew <= 16:
        raise ValueError(f"Measured positive slew rate is {slew:.3g} V/us, expected about 13 V/us")
    print(f"Transient check: measured positive slew rate={slew:.2f} V/us")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_tests.py <LTspice simulation output directory>")
    directory = Path(sys.argv[1])
    check_ac(directory / "tl072_ac.raw")
    check_transient(directory / "tl072_transient.raw")


if __name__ == "__main__":
    main()
