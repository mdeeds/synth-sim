# Circuit simulation and schematic workflow

These circuits are built from the behavioral SPICE models under `..\models`,
with pin order and intended connections documented in each `.cir` file. Treat
model results as approximations: compare the simulated operating range and
waveforms with the datasheet before relying on them in hardware.

## Tools on this Windows workstation

- **LTspice:** `C:\Users\mdeed\AppData\Local\Programs\ADI\LTspice\LTspice.exe`.
  The circuit runner scripts use its batch mode and ASCII raw output.
- **KiCad CLI:** `C:\Users\mdeed\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe`.
  Use `sch erc`, `sch export pdf`, `sch export svg`, or `sch export netlist`
  to check and render a `.kicad_sch`.
- **Python:** `python` on PATH. The plot scripts use the standard library and
  read LTspice ASCII `.raw` data to create CSV and SVG outputs; CSVs are
  post-processed simulation data, not files exported directly by LTspice.
- **NGspice:** not found on PATH or in the usual install directories checked
  on this workstation. The current `.cir` files are run and validated with
  LTspice; do not assume they have been tested with NGspice.

## Existing validation entry points

- J111 datasheet circuit: `models\j11\scripts\run_figure8.ps1`.
- TL072 tests: `models\tl072\scripts\run_tests.ps1`.
- LM393 tests: `models\lm393\scripts\run_tests.ps1`.
- SSM2164 transfer test: `models\2164\scripts\run_transfer.ps1`.
- Integrator, asymmetric oscillator, and J111 sawtooth runners:
  `circuits\integrator\scripts\run_integrator.ps1`,
  `circuits\oscilator\scripts\run_oscilator.ps1`, and
  `circuits\sawtooth\scripts\run_sawtooth.ps1`.

## Repeatable process

1. Read the relevant component datasheet and model under `..\models`. Record
   the subcircuit pin order next to each `X...` instance; check it against the
   package pinout before wiring the schematic.
2. Keep the LTspice circuit (`.cir`) and the KiCad generator/schematic for a
   design in its own folder. For example, run the sawtooth simulation from the
   repository root with:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\circuits\sawtooth\scripts\run_sawtooth.ps1
   ```

   The runner invokes LTspice, saves `.raw`/`.log` under `sim`, then runs
   `scripts\plot_sawtooth.py`. Other circuits use similarly named
   `run_*.ps1` and `plot_*.py` scripts; run the corresponding pair for the
   circuit being changed.
3. Validate the generated waveform and CSV, not just LTspice's exit code.
   The plot scripts check expected thresholds, ranges, and oscillation or
   mixer behavior and report measured values. If a check fails, inspect the
   relevant saved signals in `sim\*.csv` and adjust/test the circuit before
   updating documentation with measurements.
4. Generate the KiCad schematic with its folder's `scripts\generate_schematic.py`.
   Then run ERC and exports, for example:

   ```powershell
   & 'C:\Users\mdeed\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe' sch erc --severity-all --output .\circuits\sawtooth\sim\sawtooth-erc.rpt .\circuits\sawtooth\sawtooth.kicad_sch
   & 'C:\Users\mdeed\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe' sch export pdf -o .\circuits\sawtooth\sawtooth.pdf .\circuits\sawtooth\sawtooth.kicad_sch
   & 'C:\Users\mdeed\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe' sch export svg -o .\circuits\sawtooth .\circuits\sawtooth\sawtooth.kicad_sch
   ```

   Resolve all ERC errors and warnings; also inspect the exported schematic and
   confirm each wire/net agrees with the SPICE circuit. ERC does not validate
   the electrical behavior of behavioral SPICE models.
5. Keep measured values, run commands, and model limitations in that circuit
   folder's README. Put transient data, plots, and ERC reports in `sim`.

The sawtooth example is documented in [sawtooth README](./sawtooth/README.md);
the earlier dual-comparator oscillator is in [oscilator README](./oscilator/README.md).
