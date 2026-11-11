# LM393 Dual Comparator

`LM393.lib` models a classic LM393 dual comparator using the DIP-8 pin order
from the TI datasheet:

| Pin | Name | Pin | Name |
|---:|---|---:|---|
| 1 | OUT1 | 5 | IN2+ |
| 2 | IN1- | 6 | IN2- |
| 3 | IN1+ | 7 | OUT2 |
| 4 | GND | 8 | VCC |

Outputs are open collector, so each output needs an external pull-up. The
behavioral model uses typical classic-LM393 values: 2 mV input offset, 25 nA
input bias current, 0.8 mA total supply current, and approximately 1.3 us
propagation delay. It provides threshold polarity, output saturation, and
open-collector behavior, but is not a transistor-level model and does not
reproduce input protection clamps, current limiting, saturation recovery, or
temperature corners. The PDF also documents LM393B/A variants with different
limits; this default model represents the classic LM393.

Run `scripts\run_tests.ps1` to batch-simulate the DC threshold and transient
response tests with LTspice. The script checks open-collector output states,
switching threshold, and propagation delay.
