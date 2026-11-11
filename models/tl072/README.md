# TL072 Dual Operational Amplifier

`TL072.lib` is a pin-compatible behavioral model for the standard dual
TL072. The `TL072` subcircuit and symbol follow the DIP-8 top-view pin order:

| Pin | Name | Pin | Name |
|---:|---|---:|---|
| 1 | OUT1 | 5 | IN2+ |
| 2 | IN1- | 6 | IN2- |
| 3 | IN1+ | 7 | OUT2 |
| 4 | VCC- | 8 | VCC+ |

Typical-model parameters approximate the TI datasheet: 5.25 MHz gain-bandwidth
product for the PDIP package, 13 V/us slew rate, 200 V/mV open-loop gain, 3 mV
input offset, 65 pA input bias current, and 1.5 V output headroom. The dual
amplifier quiescent current is modeled as 2.8 mA total at +/-15 V.

This macromodel includes finite open-loop gain, dominant-pole bandwidth,
slew-rate limiting, input bias and offset, output headroom, and output
resistance. It is not a transistor-level model and does not model noise,
distortion, protection behavior, load-dependent swing, or production
variation. The TL072 datasheet distinguishes classic and H-suffix devices;
this model targets typical standard TL072 behavior.

Run `scripts\run_tests.ps1` to batch-simulate the unity-gain AC response and
large-signal transient tests. The checks verify approximately 5.25 MHz
closed-loop bandwidth and 13 V/us slew rate.
