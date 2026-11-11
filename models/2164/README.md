# SSM2164 / AS2164

This package contains a four-channel, current-mode LTspice macromodel for the
SSM2164/AS2164 quad voltage-controlled amplifier. The 16-pin subcircuit and
symbol use the datasheet's physical pin numbering:

| Pin | Name | Pin | Name |
|---:|---|---:|---|
| 1 | MODE | 9 | VEE |
| 2 | IIN1 | 10 | IIN3 |
| 3 | VC1 | 11 | VC3 |
| 4 | IOUT1 | 12 | IOUT3 |
| 5 | IOUT2 | 13 | IOUT4 |
| 6 | VC2 | 14 | VC4 |
| 7 | IIN2 | 15 | IIN4 |
| 8 | GND | 16 | VCC |

Positive current entering an `IIN` pin produces positive current sourced from
the corresponding `IOUT` pin. The typical control law from the datasheets is

```text
IOUT = IIN * exp(-VC / 0.2865 V)
```

This corresponds to the specified -33 mV/dB control constant and unity gain at
VC = 0 V. The control-input resistance defaults to 5 kOhm (SSM2164 datasheet);
set `RVC=10.5k` on the subcircuit instance for the AS2164 datasheet's stated
control-input resistance.

The model is an idealized behavioral VCA. It models the four current transfer
paths, control-input loading, approximate supply current, datasheet
gain-range limits, and approximate output-pin compliance using antiparallel
diode clamps to ground. Output voltage is consequently limited to roughly
±0.6 V depending on current. Bandwidth, distortion, noise, channel
mismatch, and Class A/AB behavior are not modeled.

Run `scripts\run_transfer.ps1` to batch-simulate `vca_transfer.cir` with LTspice.
The workflow generates `vca_transfer.svg` and `sim\data\vca_transfer.csv`,
and checks the simulated currents against the exponential law and both
datasheets' control slopes and gain limits for four different input-current
levels over a -3 V to +3 V control sweep. The output-current chart uses a
logarithmic vertical scale to show the full attenuation range.

The 1 kHz, +/-5 V channel-1 integrator example is in
`circuits\integrator\integrator_1khz.cir`. Run
`circuits\integrator\scripts\run_integrator.ps1` to simulate it and generate
voltage/current plots and CSV data under `circuits\integrator\sim`. The
simulation uses VC=+0.774 V, the sketched 30 kOhm input resistor and
500 Ohm/560 pF shunt branch, and a TL072 with 560 pF capacitive feedback.
The plot shows the 2164 IOUT1 pin voltage separately from the TL072 OUT
voltage. The LTspice run keeps the inverting node near ground and targets
approximately ±5 V at OUT. The automated checks also verify IOUT1 stays
within the approximate ±0.6 V compliance range; in this feedback circuit it
is held within a few millivolts of ground. The integrator has no DC feedback
path, so DC input current or input offset can eventually drive it into
saturation. The TL072 model is behavioral and does not model input common-mode
limits or overload recovery; simulations after a large overload are therefore
not reliable representations of the physical amplifier.
