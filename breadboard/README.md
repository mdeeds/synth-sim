# SPICE breadboard layout

This small JavaScript/SVG app reads a SPICE `.cir` file and lays out its
components on breadboard holes. Component pins and bridge locations snap to
the 50-column grid. Horizontal jumpers connect columns; the five-hole strips
provide the vertical connections within each half. A cross-gap bridge is a
straight vertical wire from an E-row column to the matching F-row column.
IC subcircuit pins are read from `.SUBCKT` declarations in included models.
Resistor pins are four grid steps apart (for example, columns 10 and 14);
capacitor and diode pins remain two steps apart, while three-pin transistors
span three adjacent columns.

## Run

From the repository root:

```powershell
python .\breadboard\server.py
```

Open <http://127.0.0.1:8000/>. By default, the server opens
`circuits\sawtooth\sawtooth.cir`. To use another circuit:

```powershell
python .\breadboard\server.py --circuit .\circuits\integrator\integrator_1khz.cir --port 8001
```

Drag components to move them between hole positions; drag a bridge handle to
move it to another column. Click to select a component and **Shift-click** to
add or remove it from the selection. Arrow keys move selected parts one grid
unit; ICs move only left and right. Press **X** to flip selected horizontal
non-IC parts. Press **R** to toggle between horizontal and vertical placement
for selected two-pin parts with exactly one terminal connected directly to
VCC, VEE, or GND. A vertical part places its rail terminal on the rail and its
other terminal at row A or J on the same side of the board. **Save layout**
overwrites a `.layout.json` file
beside the selected circuit; the server reads that layout at startup. The
VCC/VEE source symbols are omitted because their rails are implied. The `.cir`
file is otherwise left untouched by the app. Red parts or wires indicate
overlapping placements or connections that need attention.

Press **W** to toggle between breadboard wiring and ratsnest modes. Ratsnest
mode draws straight connections between component pins and vertical drops to
the nearest matching power or ground rail; it does not change saved placements.
Press **P** to switch between full color and a black-on-white print view. In
print view the board and page use only black and white; browser printing hides
the app controls and keeps the board on a white page.

The board shows VCC, GND, and VEE rails, five-hole vertical strips, and a
center gap for ICs and bridge wires. Zero-volt sources whose other terminal is
ground become direct ground connections. Other zero-volt sources are omitted
from the board and their two nodes are treated as one net, so test-point
sources such as VIMON and VQMON do not appear as components or interrupt the
wiring. The view is a layout aid; check the assembled circuit and power-rail
connections before applying power.
