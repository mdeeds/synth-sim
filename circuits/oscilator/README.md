# SSM2164/TL072 Asymmetric Oscillator

`oscilator.cir` combines the existing channel-1 SSM2164/TL072 integrator with
two LM393 comparators. The first comparator is a Schmitt trigger with its
open-collector low rail at -15 V, a +15 V pull-up, and a 100 kOhm/100 kOhm
feedback divider referenced to 0 V. This gives nominal switching thresholds
near +/-7.5 V. The second comparator inverts the first output to drive SQ.

The 20 kOhm trim is represented by two resistors with `TRIM=0.30`, the
fraction of total resistance from SQ to the wiper. SQ drives the integrator
input through the 33 kOhm resistor, preserving the 30 kOhm input resistor and
500 Ohm / 560 pF shunt network from `circuits\integrator`. The 2164 control
voltage is 0.774 V.

Run `scripts\run_oscilator.ps1` to batch-simulate the circuit and generate an
SVG plot and CSV data in `sim`. The check measures the steady-state period,
asymmetry, Schmitt thresholds, and 2164 output-pin compliance. The output is a
behavioral LTspice simulation; it does not include physical parasitics or
component tolerances.

## KiCad schematic

Open `oscilator.kicad_pro` in KiCad, then open `oscilator.kicad_sch`. The
schematic uses the self-contained `Oscillator.kicad_sym` library registered
through `sym-lib-table`. `oscilator.pdf` and `oscilator.svg` are rendered
previews. Regenerate the schematic with
`python scripts\generate_schematic.py`; KiCad CLI exports and ERC can then be
run against the generated schematic. The schematic's net labels follow the
LTspice circuit, including the bipolar LM393 supply connection.
