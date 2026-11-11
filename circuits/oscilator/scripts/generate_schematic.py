import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMATIC = ROOT / "oscilator.kicad_sch"
PROJECT = "oscilator"


def uid():
    return str(uuid.uuid4())


def quote(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def font(size=1.27):
    return f"(effects (font (size {size} {size})))"


def embedded_symbol(name, reference, description, body, pins):
    lib_id = f"Oscillator:{name}"
    properties = [
        f'(property "Reference" {quote(reference)} (at 0 0 0) {font()} (hide yes))',
        f'(property "Value" {quote(name)} (at 0 0 0) {font()} (hide yes))',
        f'(property "Footprint" "" (at 0 0 0) {font()} (hide yes))',
        f'(property "Datasheet" "~" (at 0 0 0) {font()} (hide yes))',
        f'(property "Description" {quote(description)} (at 0 0 0) {font()} (hide yes))',
    ]
    pin_defs = []
    for number, name_, x, y, angle, electrical in pins:
        pin_defs.append(
            f'(pin passive line (at {x} {y} {angle}) (length 5.08) '
            f'(name {quote(name_)} {font()}) (number {quote(str(number))} {font()}))'
        )
    return "\n".join(
        [
            f'(symbol {quote(lib_id)}',
            '(pin_names (offset 1.016))',
            '(exclude_from_sim no)',
            '(in_bom yes)',
            '(on_board yes)',
            *properties,
            f'(symbol {quote(name + "_0_1")} {body})',
            f'(symbol {quote(name + "_1_1")} {" ".join(pin_defs)})',
            ')',
        ]
    )


def rectangle_body(width, height, text):
    label = f'(text {quote(text)} (at 0 0 0) {font(1.8)}) ' if text else ""
    return (
        f'{label}'
        f'(rectangle (start {-width/2} {-height/2}) (end {width/2} {height/2}) '
        '(stroke (width 0.508) (type default)) (fill (type background)))'
    )


def make_chip_pins(entries, x, spacing=5.08, start=17.78):
    result = []
    side_indices = {"left": 0, "right": 0}
    for number, name, side, electrical in entries:
        y = start - side_indices[side] * spacing
        side_indices[side] += 1
        if side == "left":
            result.append((number, name, -x, y, 0, electrical))
        else:
            result.append((number, name, x, y, 180, electrical))
    return result


def resistor_symbol():
    zigzag = " ".join(
        f"(xy {x} {y})"
        for x, y in [
            (-5.08, 0), (-3.81, 0), (-2.54, 1.27), (-1.27, -1.27),
            (0, 1.27), (1.27, -1.27), (2.54, 1.27), (3.81, 0), (5.08, 0),
        ]
    )
    return embedded_symbol(
        "R",
        "R",
        "Horizontal resistor",
        f'(polyline (pts {zigzag}) (stroke (width 0.254) (type default)) (fill (type none)))',
        [(1, "~", -7.62, 0, 0, "passive"), (2, "~", 7.62, 0, 180, "passive")],
    )


def capacitor_symbol():
    return embedded_symbol(
        "C",
        "C",
        "Horizontal unpolarized capacitor",
        '(polyline (pts (xy -1.27 -2.54) (xy -1.27 2.54)) '
        '(stroke (width 0.508) (type default)) (fill (type none))) '
        '(polyline (pts (xy 1.27 -2.54) (xy 1.27 2.54)) '
        '(stroke (width 0.508) (type default)) (fill (type none)))',
        [(1, "~", -7.62, 0, 0, "passive"), (2, "~", 7.62, 0, 180, "passive")],
    )


def dc_source_symbol():
    body = (
        '(circle (center 0 0) (radius 5.08) '
        '(stroke (width 0.508) (type default)) (fill (type none))) '
        f'(text {quote("+")} (at 0 1.905 0) {font(2.0)}) '
        f'(text {quote("-")} (at 0 -1.905 0) {font(2.0)})'
    )
    return embedded_symbol(
        "VDC",
        "V",
        "DC voltage source",
        body,
        [(1, "+", 0, 10.16, 270, "passive"), (2, "-", 0, -10.16, 90, "passive")],
    )


def custom_library():
    vca_pins = [
        (1, "MODE", "left", "input"),
        (2, "IIN1", "left", "input"),
        (3, "VC1", "left", "input"),
        (7, "IIN2", "left", "input"),
        (8, "GND", "left", "power_in"),
        (10, "IIN3", "left", "input"),
        (11, "VC3", "left", "input"),
        (15, "IIN4", "left", "input"),
        (4, "IOUT1", "right", "output"),
        (5, "IOUT2", "right", "output"),
        (6, "VC2", "right", "input"),
        (9, "VEE", "right", "power_in"),
        (12, "IOUT3", "right", "output"),
        (13, "IOUT4", "right", "output"),
        (14, "VC4", "right", "input"),
        (16, "VCC", "right", "power_in"),
    ]
    tl072_pins = [
        (1, "OUT1", "left", "output"),
        (2, "IN1-", "left", "input"),
        (3, "IN1+", "left", "input"),
        (4, "VCC-", "left", "power_in"),
        (5, "IN2+", "right", "input"),
        (6, "IN2-", "right", "input"),
        (7, "OUT2", "right", "output"),
        (8, "VCC+", "right", "power_in"),
    ]
    lm393_pins = [
        (1, "OUT1", "left", "open_collector"),
        (2, "IN1-", "left", "input"),
        (3, "IN1+", "left", "input"),
        (4, "GND", "left", "power_in"),
        (5, "IN2+", "right", "input"),
        (6, "IN2-", "right", "input"),
        (7, "OUT2", "right", "open_collector"),
        (8, "VCC", "right", "power_in"),
    ]
    symbols = [
        resistor_symbol(),
        capacitor_symbol(),
        dc_source_symbol(),
        embedded_symbol(
            "SSM2164",
            "U",
            "SSM2164 quad voltage-controlled current amplifier, DIP-16 pin order",
            rectangle_body(30.48, 45.72, ""),
            make_chip_pins(vca_pins, 20.32, 5.08, 17.78),
        ),
        embedded_symbol(
            "TL072",
            "U",
            "TL072 dual operational amplifier, DIP-8 pin order",
            rectangle_body(30.48, 25.4, ""),
            make_chip_pins(tl072_pins, 20.32, 5.08, 7.62),
        ),
        embedded_symbol(
            "LM393",
            "U",
            "LM393 dual comparator, DIP-8 pin order; output open collector",
            rectangle_body(30.48, 25.4, ""),
            make_chip_pins(lm393_pins, 20.32, 5.08, 7.62),
        ),
    ]
    return "\n".join(symbols)


def write_library():
    definitions = custom_library().replace('(symbol "Oscillator:', '(symbol "')
    (ROOT / "Oscillator.kicad_sym").write_text(
        f'(kicad_symbol_lib (version 20231120) (generator "kicad_symbol_editor") {definitions})',
        encoding="utf-8",
    )
    (ROOT / "sym-lib-table").write_text(
        '(sym_lib_table (version 7) '
        '(lib (name "Oscillator") (type "KiCad") '
        '(uri "${KIPRJMOD}/Oscillator.kicad_sym") (options "") '
        '(descr "Local symbols for the SSM2164 oscillator")))\n',
        encoding="utf-8",
    )
    (ROOT / f"{PROJECT}.kicad_pro").write_text("{}\n", encoding="utf-8")


class Schematic:
    def __init__(self):
        self.root_uuid = uid()
        self.objects = []

    def wire(self, x1, y1, x2, y2):
        self.objects.append(
            f'(wire (pts (xy {x1:.4f} {y1:.4f}) (xy {x2:.4f} {y2:.4f})) '
            f'(stroke (width 0) (type default)) (uuid {quote(uid())}))'
        )

    def label(self, net, x, y, justification="left"):
        self.objects.append(
            f'(label {quote(net)} (at {x:.4f} {y:.4f} 0) '
            f'(effects (font (size 1.27 1.27)) (justify {justification} bottom)) '
            f'(uuid {quote(uid())}))'
        )

    def note(self, text, x, y, size=1.5):
        self.objects.append(
            f'(text {quote(text)} (at {x:.4f} {y:.4f} 0) '
            f'(effects (font (size {size} {size})) (justify left bottom)) '
            f'(uuid {quote(uid())}))'
        )

    def instance(self, lib_name, ref, value, x, y, pin_map, pin_positions, property_offsets=None):
        property_offsets = property_offsets or {}
        symbol_uuid = uid()
        lines = [
            '(symbol',
            f'(lib_id {quote("Oscillator:" + lib_name)})',
            f'(at {x:.4f} {y:.4f} 0)',
            '(unit 1)',
            '(exclude_from_sim no)',
            '(in_bom yes)',
            '(on_board yes)',
            '(dnp no)',
            f'(uuid {quote(symbol_uuid)})',
        ]
        for prop, val, default_offset in (
            ("Reference", ref, (0, -4.5)),
            ("Value", value, (0, 4.5)),
        ):
            dx, dy = property_offsets.get(prop, default_offset)
            lines.append(
                f'(property {quote(prop)} {quote(val)} '
                f'(at {x + dx:.4f} {y + dy:.4f} 0) '
                f'(effects (font (size 1.27 1.27)) (justify left bottom)))'
            )
        for prop in ("Footprint", "Datasheet", "Description"):
            val = "~" if prop == "Datasheet" else ""
            lines.append(
                f'(property {quote(prop)} {quote(val)} (at {x:.4f} {y:.4f} 0) '
                f'(effects (font (size 1.27 1.27)) (hide yes)))'
            )
        for pin_number, net in pin_map.items():
            local_x, local_y, side = pin_positions[pin_number]
            sx, sy = x + local_x, y - local_y
            lines.append(f'(pin {quote(str(pin_number))} (uuid {quote(uid())}))')
            if net is None:
                self.objects.append(
                    f'(no_connect (at {sx:.4f} {sy:.4f}) (uuid {quote(uid())}))'
                )
                continue
            if side in ("left", "right"):
                wire_end_x = sx + (6.35 if side == "right" else -6.35)
                self.wire(sx, sy, wire_end_x, sy)
                self.label(net, wire_end_x, sy, "left" if side == "right" else "right")
            else:
                wire_end_y = sy + (6.35 if side == "bottom" else -6.35)
                self.wire(sx, sy, sx, wire_end_y)
                self.label(net, sx, wire_end_y)
        lines.extend(
            [
                f'(instances (project {quote(PROJECT)} (path {quote("/" + self.root_uuid)} '
                f'(reference {quote(ref)}) (unit 1))))',
                ')',
            ]
        )
        self.objects.append("\n".join(lines))

    def passive(self, kind, ref, value, x, y, left_net, right_net):
        self.instance(
            kind,
            ref,
            value,
            x,
            y,
            {1: left_net, 2: right_net},
            {1: (-7.62, 0, "left"), 2: (7.62, 0, "right")},
            {"Reference": (0, -3.81), "Value": (0, 3.81)},
        )

    def render(self):
        return "\n".join(
            [
                "(kicad_sch",
                "(version 20250114)",
                '(generator "eeschema")',
                '(generator_version "10.0")',
                f'(uuid {quote(self.root_uuid)})',
                '(paper "A4")',
                '(title_block (title "SSM2164 / TL072 Asymmetric Oscillator") '
                '(date "2026-11-11") (rev "1"))',
                f'(lib_symbols {custom_library()})',
                *self.objects,
                f'(sheet_instances (path {quote("/" + self.root_uuid)} (page "1")))',
                ")",
            ]
        )


def build():
    schematic = Schematic()

    vca_pin_positions = {
        1: (-20.32, 17.78, "left"),
        2: (-20.32, 12.70, "left"),
        3: (-20.32, 7.62, "left"),
        7: (-20.32, 2.54, "left"),
        8: (-20.32, -2.54, "left"),
        10: (-20.32, -7.62, "left"),
        11: (-20.32, -12.70, "left"),
        15: (-20.32, -17.78, "left"),
        4: (20.32, 17.78, "right"),
        5: (20.32, 12.70, "right"),
        6: (20.32, 7.62, "right"),
        9: (20.32, 2.54, "right"),
        12: (20.32, -2.54, "right"),
        13: (20.32, -7.62, "right"),
        14: (20.32, -12.70, "right"),
        16: (20.32, -17.78, "right"),
    }
    lm_pin_positions = {
        1: (-20.32, 7.62, "left"),
        2: (-20.32, 2.54, "left"),
        3: (-20.32, -2.54, "left"),
        4: (-20.32, -7.62, "left"),
        5: (20.32, 7.62, "right"),
        6: (20.32, 2.54, "right"),
        7: (20.32, -2.54, "right"),
        8: (20.32, -7.62, "right"),
    }
    tl_pin_positions = {
        1: (-20.32, 7.62, "left"),
        2: (-20.32, 2.54, "left"),
        3: (-20.32, -2.54, "left"),
        4: (-20.32, -7.62, "left"),
        5: (20.32, 7.62, "right"),
        6: (20.32, 2.54, "right"),
        7: (20.32, -2.54, "right"),
        8: (20.32, -7.62, "right"),
    }

    schematic.note("DUAL-SUPPLY OSCILLATOR - LTspice macromodel-based schematic", 12.7, 12.7, 1.8)
    schematic.note("Power: VCC = +15 V, GND = 0 V, VEE = -15 V. CV1 = 0.774 V.", 12.7, 19.05)
    schematic.note("LM393 Schmitt thresholds about +/-7.5 V; second comparator inverts HYST to SQ.", 12.7, 25.4)
    schematic.note("R_TRIM = 20k total; wiper is 30% from the SQ end.", 12.7, 31.75, 1.25)
    schematic.note("Input chain: 33k, 30k, 500 ohm and 560 pF; CAP feeds back to the Schmitt trigger.", 12.7, 38.1, 1.25)

    schematic.instance(
        "VDC", "V1", "0.774 VDC",
        208.28, 142.24,
        {1: "CV", 2: "GND"},
        {1: (0, 10.16, "top"), 2: (0, -10.16, "bottom")},
        {"Reference": (8, -1.27), "Value": (8, 1.27)},
    )
    schematic.note("CV reference", 219.71, 142.24, 1.25)

    schematic.instance(
        "LM393", "U3", "LM393",
        69.85, 63.5,
        {1: "HYST", 2: "CAP", 3: "VTH", 4: "VEE",
         5: "GND", 6: "HYST", 7: "SQ", 8: "VCC"},
        lm_pin_positions,
        {"Reference": (0, -18), "Value": (0, 18)},
    )
    schematic.note("A: CAP vs VTH Schmitt trigger; B: HYST inverter", 38.1, 91.44, 1.25)

    schematic.instance(
        "SSM2164", "U1", "SSM2164",
        69.85, 152.4,
        {1: "GND", 2: "NDRIVE", 3: "CV", 7: "GND", 8: "GND",
         10: "GND", 11: "GND", 15: "GND",
         4: "SUM", 5: "GND", 6: "GND", 9: "VEE", 12: "GND",
         13: "GND", 14: "GND", 16: "VCC"},
        vca_pin_positions,
        {"Reference": (0, -29), "Value": (0, 29)},
    )
    schematic.note("Unused channels tied to GND as in LTspice test circuit.", 38.1, 187.96, 1.25)

    schematic.instance(
        "TL072", "U2", "TL072",
        160.02, 152.4,
        {1: "CAP", 2: "SUM", 3: "GND", 4: "VEE",
         5: "GND", 6: "GND", 7: None, 8: "VCC"},
        tl_pin_positions,
        {"Reference": (0, -18), "Value": (0, 18)},
    )


    passives = [
        ("R", "RPU1", "5.1k", "HYST", "VCC"),
        ("R", "RFB", "100k", "HYST", "VTH"),
        ("R", "RREF", "100k", "VTH", "GND"),
        ("R", "RPU2", "5.1k", "SQ", "VCC"),
        ("C", "CHYST", "15p", "HYST", "GND"),
        ("C", "CSQ", "15p", "SQ", "GND"),
        ("R", "R_TRIM_HI", "6k", "SQ", "WIPER"),
        ("R", "R_TRIM_LO", "14k", "WIPER", "VEE"),
        ("R", "R_SQ", "33k", "WIPER", "IN"),
        ("R", "RIN", "30k", "IN", "NDRIVE"),
        ("R", "RSHUNT", "500", "NDRIVE", "NCOMP"),
        ("C", "CCOMP", "560p", "NCOMP", "GND"),
        ("C", "CFB", "560p", "SUM", "CAP"),
    ]
    for index, (kind, ref, value, left, right) in enumerate(passives):
        x = 238.76
        y = 50.8 + index * 10.16
        schematic.passive(kind, ref, value, x, y, left, right)


    write_library()
    SCHEMATIC.write_text(schematic.render(), encoding="utf-8")
    print(f"Wrote {SCHEMATIC}")


if __name__ == "__main__":
    build()
