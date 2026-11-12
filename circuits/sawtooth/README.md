# Fixed-Input SSM2164 Sawtooth Oscillator

`sawtooth.cir` uses the existing SSM2164/TL072 integrator with a fixed 1 V
input. A dual LM393 provides a Schmitt threshold and complementary reset
control. The J111 is connected across the feedback capacitor through a
current-limiting resistor; when enabled, it quickly returns `CAP` to the
integrator summing node. This produces a negative-going ramp and fast flyback
without changing the 2164 input current.

The second TL072 channel buffers a crossfade between `CAP` and a resistor-
scaled version of the LM393 square output. `RV1` is modeled by two 100 kOhm
resistors: `MIX=0` selects sawtooth, `MIX=1` selects square, and the default
`MIX=0.5` is an equal blend. The 20 kOhm/10 kOhm divider scales the comparator
output to approximately +/-5 V before it reaches the TL072 input, within its
input common-mode range. The square wave retains the oscillator's asymmetric
duty cycle. The TL072's modeled slew rate rounds the square-wave transitions.

Run `scripts\run_sawtooth.ps1` to simulate with LTspice and generate
`sim\sawtooth.csv` and `sim\sawtooth.svg`. The chart includes CAP and IN
voltages, comparator threshold/control levels, mixed output, 2164
input/output currents, J111 drain current, and gate voltage. The script checks
the measured period, CAP range, gate switching, crossfade tracking, and 2164
output-pin compliance. Results are from behavioral macromodels and are not a
substitute for hardware measurements.

The current model run produces approximately a 0.657 ms period (about 1.52
kHz) and a steady-state CAP range of -2.55 V to +0.09 V. The reset interval is
about 10 us.
Values depend on the included component models and their idealized behavior.

## KiCad schematic

Open `sawtooth.kicad_pro` and `sawtooth.kicad_sch`. The schematic uses
`Oscillator.kicad_sym` and `sym-lib-table`; the local symbol definitions and
pin-orientation helpers are shared with the earlier oscillator schematic.
Regenerate with `python scripts\generate_schematic.py`. `RV1` is the 100 kOhm
sawtooth-to-square crossfade control, buffered by pin 7 of the TL072. The
`V1`/`V2` sources provide the +/-15 V rails, and V4/V5 set the fixed input and
control voltage.
