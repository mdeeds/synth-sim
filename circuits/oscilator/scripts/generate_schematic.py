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


def embedded_symbol(name, reference, description, body, pins, pin_electrical=False):
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
        pin_type = electrical if pin_electrical else "passive"
        pin_defs.append(
            f'(pin {pin_type} line (at {x} {y} {angle}) (length 5.08) '
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


def make_rotated_dip_pins(entries, pin_count):
    names = {number: (name, electrical) for number, name, electrical in entries}
    if pin_count == 8:
        positions = {
            1: (-7.62, -15.24, 90),
            2: (-2.54, -15.24, 90),
            3: (2.54, -15.24, 90),
            4: (7.62, -15.24, 90),
            5: (7.62, 15.24, 270),
            6: (2.54, 15.24, 270),
            7: (-2.54, 15.24, 270),
            8: (-7.62, 15.24, 270),
        }
    elif pin_count == 16:
        positions = {
            **{
                number: (-17.78 + (number - 1) * 5.08, -15.24, 90)
                for number in range(1, 9)
            },
            **{
                number: (17.78 - (number - 9) * 5.08, 15.24, 270)
                for number in range(9, 17)
            },
        }
    else:
        raise ValueError(f"Unsupported DIP pin count: {pin_count}")
    return [
        (number, names[number][0], *positions[number], names[number][1])
        for number in range(1, pin_count + 1)
    ]


def rotated_dip_pin_positions(pin_count):
    pins = make_rotated_dip_pins(
        [(number, str(number), "passive") for number in range(1, pin_count + 1)],
        pin_count,
    )
    return {
        number: (x, y, "top" if y > 0 else "bottom")
        for number, _, x, y, _, _ in pins
    }


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


def dc_source_symbol(name="VDC", power_out_pin=None):
    body = (
        '(circle (center 0 0) (radius 5.08) '
        '(stroke (width 0.508) (type default)) (fill (type none))) '
        f'(text {quote("+")} (at 0 1.905 0) {font(2.0)}) '
        f'(text {quote("-")} (at 0 -1.905 0) {font(2.0)})'
    )
    return embedded_symbol(
        name,
        "V",
        "DC voltage source",
        body,
        [
            (1, "+", 0, 10.16, 270, "power_out" if power_out_pin == 1 else "passive"),
            (2, "-", 0, -10.16, 90, "power_out" if power_out_pin == 2 else "passive"),
        ],
        pin_electrical=power_out_pin is not None,
    )


def power_symbol(name, library_name=None, pin_type="power_in"):
    library_name = library_name or name
    if name == "+15V":
        body = (
            '(polyline (pts (xy -0.762 1.27) (xy 0 2.54)) '
            '(stroke (width 0) (type default)) (fill (type none))) '
            '(polyline (pts (xy 0 2.54) (xy 0.762 1.27)) '
            '(stroke (width 0) (type default)) (fill (type none))) '
            '(polyline (pts (xy 0 0) (xy 0 2.54)) '
            '(stroke (width 0) (type default)) (fill (type none)))'
        )
    elif name == "-15V":
        body = (
            '(polyline (pts (xy 0 0) (xy 0 1.27) (xy 0.762 1.27) '
            '(xy 0 2.54) (xy -0.762 1.27) (xy 0 1.27)) '
            '(stroke (width 0) (type default)) (fill (type outline)))'
        )
    elif name == "GND":
        body = (
            '(polyline (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) '
            '(xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)) '
            '(stroke (width 0) (type default)) (fill (type none)))'
        )
    else:
        raise ValueError(f"Unsupported power symbol: {name}")
    return (
        f'(symbol {quote("Oscillator:" + library_name)} (power global) '
        '(pin_numbers (hide yes)) (pin_names (offset 0) (hide yes)) '
        '(exclude_from_sim no) (in_bom yes) (on_board yes) '
        f'(property "Reference" "#PWR" (at 0 -6.35 0) {font()} (hide yes)) '
        f'(property "Value" {quote(name)} (at 0 -3.81 0) {font()}) '
        f'(property "Footprint" "" (at 0 0 0) {font()} (hide yes)) '
        f'(property "Datasheet" "" (at 0 0 0) {font()} (hide yes)) '
        f'(property "Description" {quote("Global power symbol for " + name)} '
        f'(at 0 0 0) {font()} (hide yes)) '
        f'(symbol {quote(library_name + "_0_1")} {body}) '
        f'(symbol {quote(library_name + "_1_1")} '
        f'(pin {pin_type} line (at 0 0 {"270" if name == "GND" else "90"}) (length 0) '
        '(name "" (effects (font (size 1.27 1.27)))) '
        '(number "1" (effects (font (size 1.27 1.27))))))'
        ')'
    )


def custom_library():
    vca_pins = [
        (1, "MODE", "input"),
        (2, "IIN1", "input"),
        (3, "VC1", "input"),
        (4, "IOUT1", "output"),
        (5, "IOUT2", "output"),
        (6, "VC2", "input"),
        (7, "IIN2", "input"),
        (8, "GND", "power_in"),
        (9, "VEE", "power_in"),
        (10, "IIN3", "input"),
        (11, "VC3", "input"),
        (12, "IOUT3", "output"),
        (13, "IOUT4", "output"),
        (14, "VC4", "input"),
        (15, "IIN4", "input"),
        (16, "VCC", "power_in"),
    ]
    tl072_pins = [
        (1, "OUT1", "output"),
        (2, "IN1-", "input"),
        (3, "IN1+", "input"),
        (4, "VCC-", "power_in"),
        (5, "IN2+", "input"),
        (6, "IN2-", "input"),
        (7, "OUT2", "output"),
        (8, "VCC+", "power_in"),
    ]
    lm393_pins = [
        (1, "OUT1", "open_collector"),
        (2, "IN1-", "input"),
        (3, "IN1+", "input"),
        (4, "GND", "power_in"),
        (5, "IN2+", "input"),
        (6, "IN2-", "input"),
        (7, "OUT2", "open_collector"),
        (8, "VCC", "power_in"),
    ]
    symbols = [
        resistor_symbol(),
        capacitor_symbol(),
        dc_source_symbol(),
        dc_source_symbol("VDC_POS", 1),
        dc_source_symbol("VDC_NEG", 2),
        dc_source_symbol("VDC_CV", 2),
        power_symbol("GND"),
        power_symbol("+15V"),
        power_symbol("-15V"),
        embedded_symbol(
            "SSM2164",
            "U",
            "SSM2164 quad voltage-controlled current amplifier, DIP-16 pin order",
            rectangle_body(45.72, 20.32, ""),
            make_rotated_dip_pins(vca_pins, 16),
        ),
        embedded_symbol(
            "TL072",
            "U",
            "TL072 dual operational amplifier, DIP-8 pin order",
            rectangle_body(20.32, 20.32, ""),
            make_rotated_dip_pins(tl072_pins, 8),
        ),
        embedded_symbol(
            "LM393",
            "U",
            "LM393 dual comparator, DIP-8 pin order; output open collector",
            rectangle_body(20.32, 20.32, ""),
            make_rotated_dip_pins(lm393_pins, 8),
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
        self.power_index = 0

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

    def power(self, name, x, y, angle=0):
        self.power_index += 1
        ref = f"#PWR{self.power_index:02d}"
        symbol_uuid = uid()
        self.objects.append(
            "\n".join(
                [
                    "(symbol",
                    f'(lib_id {quote("Oscillator:" + name)})',
                    f"(at {x:.4f} {y:.4f} {angle})",
                    "(unit 1)",
                    "(exclude_from_sim no)",
                    "(in_bom no)",
                    "(on_board no)",
                    "(dnp no)",
                    f"(uuid {quote(symbol_uuid)})",
                    f'(property "Reference" {quote(ref)} '
                    f'(at {x:.4f} {y - 3.81:.4f} 0) '
                    f'{font()} (hide yes))',
                    f'(property "Value" {quote(name)} '
                    f'(at {x:.4f} {y - 3.81:.4f} 0) {font()})',
                    f'(property "Footprint" "" (at {x:.4f} {y:.4f} 0) '
                    f'{font()} (hide yes))',
                    f'(property "Datasheet" "" (at {x:.4f} {y:.4f} 0) '
                    f'{font()} (hide yes))',
                    f'(pin "1" (uuid {quote(uid())}))',
                    f'(instances (project {quote(PROJECT)} (path '
                    f'{quote("/" + self.root_uuid)} (reference {quote(ref)}) '
                    "(unit 1))))",
                    ")",
                ]
            )
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
                if net in ("GND", "+15V", "-15V"):
                    self.wire(sx, sy, wire_end_x, sy)
                    angle = 180 if net == "-15V" else 0
                    self.power(
                        net,
                        wire_end_x,
                        sy,
                        angle,
                    )
                else:
                    self.wire(sx, sy, wire_end_x, sy)
                    self.label(net, wire_end_x, sy, "left" if side == "right" else "right")
            else:
                wire_end_y = sy + (6.35 if side == "bottom" else -6.35)
                if net in ("GND", "+15V", "-15V"):
                    self.wire(sx, sy, sx, wire_end_y)
                    angle = 180 if net == "-15V" else 0
                    self.power(
                        net,
                        sx,
                        wire_end_y,
                        angle,
                    )
                else:
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

    vca_pin_positions = rotated_dip_pin_positions(16)
    lm_pin_positions = rotated_dip_pin_positions(8)
    tl_pin_positions = rotated_dip_pin_positions(8)

    schematic.note("DUAL-SUPPLY OSCILLATOR - LTspice macromodel-based schematic", 12.7, 12.7, 1.8)
    schematic.note("Power rails: +15 V, GND = 0 V, -15 V. CV1 = 0.774 V.", 12.7, 19.05)
    schematic.note("LM393 Schmitt thresholds about +/-7.5 V; second comparator inverts HYST to SQ.", 12.7, 25.4)
    schematic.note("R_TRIM = 20k total; wiper is 30% from the SQ end.", 12.7, 31.75, 1.25)
    schematic.note("Input chain: 33k, 30k, 500 ohm and 560 pF; CAP feeds back to the Schmitt trigger.", 12.7, 38.1, 1.25)

    schematic.instance(
        "VDC_CV", "V1", "0.774 VDC",
        208.28, 142.24,
        {1: "CV", 2: "GND"},
        {1: (0, 10.16, "top"), 2: (0, -10.16, "bottom")},
        {"Reference": (8, -1.27), "Value": (8, 1.27)},
    )
    schematic.note("CV reference", 219.71, 142.24, 1.25)

    schematic.instance(
        "VDC_POS", "V2", "15 VDC",
        190.5, 76.2,
        {1: "+15V", 2: "GND"},
        {1: (0, 10.16, "top"), 2: (0, -10.16, "bottom")},
        {"Reference": (7.62, -1.27), "Value": (7.62, 1.27)},
    )
    schematic.instance(
        "VDC_NEG", "V3", "15 VDC",
        215.9, 76.2,
        {1: "GND", 2: "-15V"},
        {1: (0, 10.16, "top"), 2: (0, -10.16, "bottom")},
        {"Reference": (7.62, -1.27), "Value": (7.62, 1.27)},
    )

    schematic.instance(
        "LM393", "U3", "LM393",
        69.85, 63.5,
        {1: "HYST", 2: "CAP", 3: "VTH", 4: "-15V",
         5: "GND", 6: "HYST", 7: "SQ", 8: "+15V"},
        lm_pin_positions,
        {"Reference": (0, -1.905), "Value": (0, 1.905)},
    )
    schematic.note("A: CAP vs VTH Schmitt trigger; B: HYST inverter", 38.1, 91.44, 1.25)

    schematic.instance(
        "SSM2164", "U1", "SSM2164",
        69.85, 152.4,
        {1: "GND", 2: "NDRIVE", 3: "CV", 7: "GND", 8: "GND",
         10: "GND", 11: "GND", 15: "GND",
         4: "SUM", 5: "GND", 6: "GND", 9: "-15V", 12: "GND",
         13: "GND", 14: "GND", 16: "+15V"},
        vca_pin_positions,
        {"Reference": (-10.16, -1.27), "Value": (10.16, -1.27)},
    )
    schematic.note("Unused channels tied to GND as in LTspice test circuit.", 38.1, 187.96, 1.25)

    schematic.instance(
        "TL072", "U2", "TL072",
        160.02, 152.4,
        {1: "CAP", 2: "SUM", 3: "GND", 4: "-15V",
         5: "GND", 6: "GND", 7: None, 8: "+15V"},
        tl_pin_positions,
        {"Reference": (0, -1.905), "Value": (0, 1.905)},
    )


    passives = [
        ("R", "RPU1", "5.1k", "HYST", "+15V"),
        ("R", "RFB", "100k", "HYST", "VTH"),
        ("R", "RREF", "100k", "VTH", "GND"),
        ("R", "RPU2", "5.1k", "SQ", "+15V"),
        ("C", "CHYST", "15p", "HYST", "GND"),
        ("C", "CSQ", "15p", "SQ", "GND"),
        ("R", "R_TRIM_HI", "6k", "SQ", "WIPER"),
        ("R", "R_TRIM_LO", "14k", "WIPER", "-15V"),
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
