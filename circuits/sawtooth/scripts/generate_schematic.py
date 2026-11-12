import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "oscilator" / "scripts" / "generate_schematic.py"
SPEC = importlib.util.spec_from_file_location("oscillator_schematic", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load shared KiCad symbol helpers from {SOURCE}")
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)
generator.ROOT = ROOT
generator.SCHEMATIC = ROOT / "sawtooth.kicad_sch"
generator.PROJECT = "sawtooth"

original_custom_library = generator.custom_library


def custom_library():
    jfet = generator.embedded_symbol(
        "J111",
        "Q",
        "J111 N-channel depletion JFET, Drain/Gate/Source subcircuit order",
        generator.rectangle_body(15.24, 15.24, "J111"),
        [
            (1, "D", -7.62, -5.08, 0, "passive"),
            (2, "G", -7.62, 5.08, 0, "passive"),
            (3, "S", 7.62, 0, 180, "passive"),
        ],
    )
    zigzag = " ".join(
        f"(xy {x} {y})"
        for x, y in [
            (-5.08, 0), (-3.81, 0), (-2.54, 1.27), (-1.27, -1.27),
            (0, 1.27), (1.27, -1.27), (2.54, 1.27), (3.81, 0), (5.08, 0),
        ]
    )
    pot = generator.embedded_symbol(
        "POT",
        "R",
        "Linear potentiometer for sawtooth/square crossfade",
        f'(polyline (pts {zigzag}) (stroke (width 0.254) (type default)) (fill (type none))) '
        '(polyline (pts (xy 0 -8.89) (xy 0 -2.54) (xy 1.27 -1.27)) '
        '(stroke (width 0.254) (type default)) (fill (type none)))',
        [
            (1, "SAW", -7.62, 0, 0, "passive"),
            (2, "SQDIV", 7.62, 0, 180, "passive"),
            (3, "WIPER", 0, -13.97, 90, "passive"),
        ],
    )
    return original_custom_library() + "\n" + jfet + "\n" + pot


generator.custom_library = custom_library


def build():
    schematic = generator.Schematic()
    vca_positions = generator.rotated_dip_pin_positions(16)
    dip8_positions = generator.rotated_dip_pin_positions(8)

    schematic.note("FIXED-INPUT SAWTOOTH OSCILLATOR WITH POTENTIOMETER CROSSFADE", 12.7, 12.7, 1.8)
    schematic.note("The SSM2164 input is held at 1 V; the J111 rapidly resets the integrator capacitor.", 12.7, 19.05)
    schematic.note("LM393 Schmitt thresholds are approximately 0 V and -2.5 V; reset occurs near 1.5 kHz.", 12.7, 25.4, 1.25)
    schematic.note("RV1 crossfades the sawtooth to a scaled comparator square wave; U2B buffers the wiper.", 12.7, 31.75, 1.25)
    schematic.note("Supply rails: +15 V, GND = 0 V, -15 V. CV1 = 0.774 V.", 12.7, 38.1, 1.25)
    schematic.note("J111 source connects to the integrator summing node; its gate is driven through 100 kOhm.", 12.7, 44.45, 1.25)

    schematic.instance(
        "LM393", "U3", "LM393",
        68.58, 76.2,
        {1: "HYST", 2: "VTH", 3: "CAP", 4: "-15V",
         5: "GND", 6: "HYST", 7: "RESET", 8: "+15V"},
        dip8_positions,
        {"Reference": (0, -1.905), "Value": (0, 1.905)},
    )
    schematic.note("A: negative-ramp Schmitt trigger; B: HYST inverter", 38.1, 105.41, 1.2)

    schematic.instance(
        "SSM2164", "U1", "SSM2164",
        68.58, 158.75,
        {1: "GND", 2: "NDRIVE", 3: "CV", 4: "SUM",
         5: "GND", 6: "GND", 7: "GND", 8: "GND",
         9: "-15V", 10: "GND", 11: "GND", 12: "GND",
         13: "GND", 14: "GND", 15: "GND", 16: "+15V"},
        vca_positions,
        {"Reference": (-10.16, -1.27), "Value": (10.16, -1.27)},
    )
    schematic.note("Unused channels tied to GND as in the LTspice model test circuit.", 38.1, 194.31, 1.2)

    schematic.instance(
        "TL072", "U2", "TL072",
        158.75, 158.75,
        {1: "CAP", 2: "SUM", 3: "GND", 4: "-15V",
         5: "MIXW", 6: "MIXOUT", 7: "MIXOUT", 8: "+15V"},
        dip8_positions,
        {"Reference": (0, -1.905), "Value": (0, 1.905)},
    )

    schematic.instance(
        "J111", "Q1", "J111",
        209.55, 119.38,
        {1: "DRESET", 2: "GATE", 3: "SUM"},
        {
            1: (-7.62, -5.08, "left"),
            2: (-7.62, 5.08, "left"),
            3: (7.62, 0, "right"),
        },
        {"Reference": (0, -10.16), "Value": (0, 10.16)},
    )

    schematic.instance(
        "VDC", "V4", "1 VDC",
        198.12, 180.34,
        {1: "IN", 2: "GND"},
        {1: (0, 10.16, "top"), 2: (0, -10.16, "bottom")},
        {"Reference": (8, -1.27), "Value": (8, 1.27)},
    )
    schematic.instance(
        "VDC_CV", "V5", "0.774 VDC",
        226.06, 180.34,
        {1: "CV", 2: "GND"},
        {1: (0, 10.16, "top"), 2: (0, -10.16, "bottom")},
        {"Reference": (8, -1.27), "Value": (8, 1.27)},
    )
    schematic.instance(
        "VDC_POS", "V1", "15 VDC",
        203.2, 68.58,
        {1: "+15V", 2: "GND"},
        {1: (0, 10.16, "top"), 2: (0, -10.16, "bottom")},
        {"Reference": (7.62, -1.27), "Value": (7.62, 1.27)},
    )
    schematic.instance(
        "VDC_NEG", "V2", "15 VDC",
        231.14, 68.58,
        {1: "GND", 2: "-15V"},
        {1: (0, 10.16, "top"), 2: (0, -10.16, "bottom")},
        {"Reference": (7.62, -1.27), "Value": (7.62, 1.27)},
    )
    schematic.instance(
        "POT", "RV1", "100k linear",
        224.79, 144.78,
        {1: "CAP", 2: "SQDIV", 3: "MIXW"},
        {
            1: (-7.62, 0, "left"),
            2: (7.62, 0, "right"),
            3: (0, -13.97, "top"),
        },
        {"Reference": (0, -8.89), "Value": (0, 8.89)},
    )

    passives = [
        ("R", "RPU1", "10k", "HYST", "+15V"),
        ("R", "RPU2", "10k", "RESET", "+15V"),
        ("R", "RTH", "1Meg", "-15V", "VTH"),
        ("R", "RREF", "100k", "VTH", "GND"),
        ("R", "RFB", "1Meg", "VTH", "RESET"),
        ("R", "RIN", "30k", "IN", "NDRIVE"),
        ("R", "RSHUNT", "500", "NDRIVE", "NCOMP"),
        ("C", "CCOMP", "560p", "NCOMP", "GND"),
        ("C", "CFB", "560p", "CAP", "SUM"),
        ("R", "RGATE", "100k", "RESET", "GATE"),
        ("R", "RRESET", "220", "CAP", "DRESET"),
        ("R", "RSQ1", "20k", "RESET", "SQDIV"),
        ("R", "RSQ2", "10k", "SQDIV", "GND"),
    ]
    for index, (kind, ref, value, left, right) in enumerate(passives):
        schematic.passive(kind, ref, value, 259.08, 96.52 + index * 8.89, left, right)

    generator.write_library()
    text = schematic.render().replace(
        "SSM2164 / TL072 Asymmetric Oscillator",
        "Fixed-Input SSM2164 Sawtooth Oscillator with Crossfade",
    )
    generator.SCHEMATIC.write_text(text, encoding="utf-8")
    print(f"Wrote {generator.SCHEMATIC}")


if __name__ == "__main__":
    build()
