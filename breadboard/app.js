(function (root) {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const WIDTH = 1900;
  const X_MIN = 90;
  const X_MAX = 1810;
  const COLUMN_COUNT = 50;
  const COLUMN_PITCH = (X_MAX - X_MIN) / (COLUMN_COUNT - 1);
  const TOP_ROWS = [154, 188, 222, 256, 290];
  const BOTTOM_ROWS = [662, 696, 730, 764, 798];
  const COLORS = ["#d44731", "#3277bd", "#7d4cb5", "#159277", "#ce7a16", "#bd477d", "#367c42", "#575eb9"];
  const PIN_COUNTS = { r: 2, c: 2, l: 2, v: 2, i: 2, d: 2, q: 3, j: 3, m: 4, b: 2, e: 4, f: 2, g: 2, h: 2, s: 4, w: 2 };
  let selectedComponentIds = new Set();
  let wiringMode = "breadboard";
  let printMode = false;

  function icWidth(component) {
    return Math.max(100, (component.nodes.length / 2 - 1) * COLUMN_PITCH + 68);
  }

  function columnX(column) {
    return X_MIN + column * COLUMN_PITCH;
  }

  function columnAt(x) {
    return Math.max(0, Math.min(COLUMN_COUNT - 1, Math.round((x - X_MIN) / COLUMN_PITCH)));
  }

  function pinOffsets(component, flipped = false) {
    let offsets;
    if (component.nodes.length === 2 && component.kind === "r") offsets = [-2, 2];
    else if (component.nodes.length === 2) offsets = [-1, 1];
    else if (component.nodes.length === 3) offsets = [-1, 0, 1];
    else if (component.nodes.length === 4) offsets = [-2, -1, 1, 2];
    else offsets = component.nodes.map((_, index) => index - (component.nodes.length - 1) / 2);
    return flipped ? offsets.reverse() : offsets;
  }

  function componentBodyWidth(component) {
    if (component.nodes.length > 2) return 66;
    return component.kind === "r" ? 70 : 50;
  }

  function railPinIndex(component) {
    if (component.isIc || component.nodes.length !== 2) return -1;
    const railPins = component.nodes
      .map((node, index) => isRail(node) ? index : -1)
      .filter(index => index >= 0);
    return railPins.length === 1 ? railPins[0] : -1;
  }

  function canRotateVertically(component) {
    return railPinIndex(component) >= 0;
  }

  function isVerticalRailPosition(component, position) {
    return Boolean(position && position.vertical === true && railPinIndex(component) >= 0);
  }

  function railY(component, position) {
    const rail = isRail(component.nodes[railPinIndex(component)]);
    if (rail === "VCC") return 46;
    if (rail === "VEE") return 912;
    return position.bank === "top" ? 83 : 875;
  }

  function edgeRowY(bank) {
    const rows = bank === "top" ? TOP_ROWS : BOTTOM_ROWS;
    return rows[bank === "top" ? 0 : 4];
  }

  function componentCenterY(component, position) {
    if (component.isIc) return 476;
    if (isVerticalRailPosition(component, position)) {
      return (railY(component, position) + edgeRowY(position.bank)) / 2;
    }
    return (position.bank === "top" ? TOP_ROWS : BOTTOM_ROWS)[position.row];
  }

  function clampStandardColumn(component, column) {
    const offsets = pinOffsets(component);
    return Math.max(-Math.min(...offsets), Math.min(COLUMN_COUNT - 1 - Math.max(...offsets), column));
  }

  function normalizePosition(component, position) {
    if (component.isIc) {
      const maxStart = Math.max(0, COLUMN_COUNT - component.nodes.length / 2);
      return {
        column: Math.max(0, Math.min(maxStart, Math.round(position.column))),
        row: 2,
        bank: "ic",
        flipped: false,
        vertical: false,
      };
    }

    const bank = position.bank === "bottom" ? "bottom" : "top";
    const vertical = railPinIndex(component) >= 0 && position.vertical === true;
    return {
      column: vertical
        ? Math.max(0, Math.min(COLUMN_COUNT - 1, Math.round(position.column)))
        : clampStandardColumn(component, Math.round(position.column)),
      row: Math.max(0, Math.min(4, Math.round(position.row))),
      bank,
      flipped: position.flipped === true,
      vertical,
    };
  }

  function activeBridgeNodes(components, positions) {
    const nodeBanks = new Map();
    for (const component of components) {
      const position = positions[component.id];
      for (let index = 0; index < component.nodes.length; index++) {
        const bank = component.isIc
          ? (index < component.nodes.length / 2 ? "top" : "bottom")
          : position.bank;
        const key = nodeKey(component.nodes[index]);
        if (!nodeBanks.has(key)) nodeBanks.set(key, new Set());
        nodeBanks.get(key).add(bank);
      }
    }
    return new Set([...nodeBanks.entries()]
      .filter(([node, banks]) => !isRail(node) && banks.size === 2)
      .map(([node]) => node));
  }

  function parseCircuit(text, subcircuits) {
    const logicalLines = [];
    const zeroVoltLinks = [];
    for (const rawLine of text.split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("*")) continue;
      if (line.startsWith("+") && logicalLines.length) {
        logicalLines[logicalLines.length - 1] += " " + line.slice(1).trim();
      } else {
        logicalLines.push(line);
      }
    }

    const components = [];
    const errors = [];
    for (const line of logicalLines) {
      if (line.startsWith(".")) continue;
      const tokens = line.split(/\s+/);
      const reference = tokens[0];
      const kind = reference[0].toLowerCase();
      if (kind === "v" && ["vcc", "vee"].includes(reference.toLowerCase())) continue;
      let nodeNames;
      let value;

      if (kind === "x") {
        const subcircuitIndex = tokens.findIndex((token, index) =>
          index > 1 && Object.prototype.hasOwnProperty.call(subcircuits, token.toLowerCase())
        );
        if (subcircuitIndex < 0) {
          errors.push(`${reference}: could not find a matching .SUBCKT pin declaration in the included models.`);
          continue;
        }
        nodeNames = tokens.slice(1, subcircuitIndex);
        const declaration = subcircuits[tokens[subcircuitIndex].toLowerCase()];
        if (nodeNames.length !== declaration.length) {
          errors.push(`${reference}: found ${nodeNames.length} nodes but ${declaration.length} model pins.`);
          continue;
        }
        value = tokens[subcircuitIndex];
      } else {
        const count = PIN_COUNTS[kind];
        if (!count) {
          errors.push(`${reference}: unsupported SPICE component type.`);
          continue;
        }
        if (tokens.length < count + 2) {
          errors.push(`${reference}: expected at least ${count} pin nodes and a value.`);
          continue;
        }
        nodeNames = tokens.slice(1, count + 1);
        value = tokens.slice(count + 1).join(" ");
      }

      if (kind === "v" && isZeroVoltageValue(value)) {
        zeroVoltLinks.push(nodeNames);
        continue;
      }

      components.push({
        id: reference,
        reference,
        kind,
        value,
        nodes: nodeNames,
        pinNames: kind === "x" ? subcircuits[value.toLowerCase()] : nodeNames.map((_, index) => `Pin ${index + 1}`),
        isIc: kind === "x" && nodeNames.length >= 6 && nodeNames.length % 2 === 0,
      });
    }

    mergeZeroVoltNodes(components, zeroVoltLinks);
    return { components, errors };
  }

  function isZeroVoltageValue(value) {
    const tokens = value.trim().split(/\s+/);
    const voltage = tokens.length === 1
      ? tokens[0]
      : tokens.length === 2 && tokens[0].toLowerCase() === "dc"
        ? tokens[1]
        : null;
    return voltage !== null && voltage !== "" && Number(voltage) === 0;
  }

  function mergeZeroVoltNodes(components, links) {
    const parents = new Map();
    const labels = new Map();
    function register(name) {
      const key = nodeKey(name);
      if (!parents.has(key)) {
        parents.set(key, key);
        labels.set(key, name);
      }
      return key;
    }

    function find(name) {
      const key = register(name);
      const parent = parents.get(key);
      if (parent !== key) parents.set(key, find(parent));
      return parents.get(key);
    }

    function priority(key) {
      if (key === "0") return 2;
      if (key === "vcc" || key === "vee") return 1;
      return 0;
    }

    for (const [left, right] of links) {
      const leftRoot = find(left);
      const rightRoot = find(right);
      if (leftRoot === rightRoot) continue;
      if (priority(rightRoot) > priority(leftRoot)) {
        parents.set(leftRoot, rightRoot);
      } else {
        parents.set(rightRoot, leftRoot);
      }
    }

    for (const component of components) {
      component.nodes = component.nodes.map(name => {
        const key = nodeKey(name);
        if (!parents.has(key)) return name;
        const root = find(key);
        if (root === "0") return "0";
        if (root === "vcc") return "VCC";
        if (root === "vee") return "VEE";
        return labels.get(root);
      });
    }
  }

  function defaultLayout(components) {
    const positions = {};
    const ics = components.filter(item => item.isIc);
    const totalPinColumns = ics.reduce((sum, component) => sum + component.nodes.length / 2, 0);
    const availableColumns = COLUMN_COUNT - 2 - totalPinColumns;
    const gap = availableColumns / (ics.length + 1);
    let icPinColumnsBefore = 0;
    const columnNodes = {
      top: Array.from({ length: COLUMN_COUNT }, () => new Set()),
      bottom: Array.from({ length: COLUMN_COUNT }, () => new Set()),
    };
    const nodeColumns = { top: new Map(), bottom: new Map() };
    const rowIntervals = { top: Array.from({ length: 5 }, () => []), bottom: Array.from({ length: 5 }, () => []) };

    function reservePins(component, position) {
      const pins = pinLocations(component, position);
      pins.forEach((pin, index) => {
        const bank = component.isIc
          ? (index < component.nodes.length / 2 ? "top" : "bottom")
          : position.bank;
        const node = nodeKey(component.nodes[index]);
        columnNodes[bank][pin.column].add(node);
        if (!nodeColumns[bank].has(node)) nodeColumns[bank].set(node, new Set());
        nodeColumns[bank].get(node).add(pin.column);
      });
    }

    ics.forEach((component, index) => {
      const half = component.nodes.length / 2;
      const column = Math.round(1 + gap * (index + 1) + icPinColumnsBefore);
      const position = { column, row: 2, bank: "ic", flipped: false };
      positions[component.id] = position;
      icPinColumnsBefore += half;
      reservePins(component, position);
    });

    const standardComponents = components.filter(component => !component.isIc);
    const bankCounts = { top: 0, bottom: 0 };
    standardComponents.forEach((component, index) => {
      const offsets = pinOffsets(component);
      let best = null;
      for (const bank of ["top", "bottom"]) {
        for (let column = -Math.min(...offsets); column < COLUMN_COUNT - Math.max(...offsets); column++) {
          for (let row = 0; row < 5; row++) {
            let score = rowIntervals[bank][row].length * 0.4 +
              Math.max(0, bankCounts[bank] - bankCounts[bank === "top" ? "bottom" : "top"]) * 0.5;
            const first = column + Math.min(...offsets);
            const last = column + Math.max(...offsets);
            for (const interval of rowIntervals[bank][row]) {
              if (first <= interval.last && interval.first <= last) score += 100;
            }
            component.nodes.forEach((name, pinIndex) => {
              const node = nodeKey(name);
              const pinColumn = column + offsets[pinIndex];
              const occupants = columnNodes[bank][pinColumn];
              if ([...occupants].some(existing => existing !== node)) score += 1000;
              const knownColumns = nodeColumns[bank].get(node);
              if (knownColumns && !knownColumns.has(pinColumn)) score += 3;
            });
            if (!best || score < best.score) best = { bank, column, row, score };
          }
        }
      }

      const position = { column: best.column, row: best.row, bank: best.bank, flipped: false };
      positions[component.id] = position;
      rowIntervals[best.bank][best.row].push({
        first: position.column + Math.min(...offsets),
        last: position.column + Math.max(...offsets),
      });
      bankCounts[best.bank]++;
      reservePins(component, position);
    });

    for (const component of components) {
      if (!positions[component.id]) throw new Error(`No layout position was assigned to ${component.id}.`);
    }
    return { version: 2, components: positions, bridges: {} };
  }

  function migrateLayout(saved, components, defaults) {
    if (!saved || typeof saved !== "object") return defaults;
    const migrated = { version: 2, components: { ...defaults.components }, bridges: {} };
    if (saved.version === 2) {
      for (const component of components) {
        const position = saved.components && saved.components[component.id];
        if (position && Number.isInteger(position.column)) {
          migrated.components[component.id] = normalizePosition(component, position);
        }
      }
      const activeBridges = activeBridgeNodes(components, migrated.components);
      for (const [node, column] of Object.entries(saved.bridges || {})) {
        const key = nodeKey(node);
        if (activeBridges.has(key) && Number.isFinite(column)) {
          migrated.bridges[key] = Math.max(0, Math.min(COLUMN_COUNT - 1, Math.round(column)));
        }
      }
      return migrated;
    }

    if (saved.version === 1) {
      for (const component of components) {
        const position = saved.components && saved.components[component.id];
        if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) continue;
        const bank = position.y < 480 ? "top" : "bottom";
        const column = component.isIc
          ? Math.round((position.x - (component.nodes.length / 2 - 1) * 29 / 2 - X_MIN) / COLUMN_PITCH)
          : columnAt(position.x);
        const rows = bank === "top" ? TOP_ROWS : BOTTOM_ROWS;
        const migratedPosition = {
          column,
          row: component.isIc ? 2 : nearestIndex(position.y, rows),
          bank: component.isIc ? "ic" : bank,
        };
        migrated.components[component.id] = normalizePosition(component, migratedPosition);
      }
      const activeBridges = activeBridgeNodes(components, migrated.components);
      for (const [node, x] of Object.entries(saved.bridges || {})) {
        const key = nodeKey(node);
        if (activeBridges.has(key) && Number.isFinite(x)) migrated.bridges[key] = columnAt(x);
      }
    }
    return migrated;
  }

  function nodeKey(name) {
    const normalized = name.toLowerCase();
    return normalized === "gnd" || normalized === "ground" ? "0" : normalized;
  }

  function isRail(node) {
    const normalized = nodeKey(node);
    if (normalized === "vcc") return "VCC";
    if (normalized === "vee") return "VEE";
    if (normalized === "0" || normalized === "gnd" || normalized === "ground") return "GND";
    return null;
  }

  function svgElement(tag, attributes, text) {
    const element = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attributes || {})) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function draw() {
    const board = document.getElementById("board");
    const { components, layout, parseErrors } = root.Breadboard.state;
    document.body.classList.toggle("print-mode", printMode);
    board.classList.toggle("print-mode", printMode);
    board.replaceChildren();

    const base = svgElement("g", {});
    board.appendChild(base);
    base.appendChild(svgElement("rect", { x: 0, y: 0, width: WIDTH, height: 960, fill: "#f7f8f6" }));

    drawRail(base, "VCC", 46, "#d84a4a");
    drawRail(base, "GND", 83, "#424a52");
    drawBank(base, TOP_ROWS, "A–E connected vertically");
    drawGap(base);
    drawBank(base, BOTTOM_ROWS, "F–J connected vertically");
    drawRail(base, "GND", 875, "#424a52");
    drawRail(base, "VEE", 912, "#3572c6");
    base.appendChild(svgElement("text", { x: 40, y: 495, class: "board-label" }, "IC CHANNEL"));

    const positions = layout.components;
    const endpoints = [];
    const issues = parseErrors.slice();
    for (const component of components) {
      const position = positions[component.id];
      if (!position || !Number.isInteger(position.column) || !Number.isInteger(position.row) ||
        !["top", "bottom", "ic"].includes(position.bank)) {
        issues.push(`${component.reference}: missing or invalid saved position.`);
        continue;
      }
      const pins = pinLocations(component, position);
      for (let index = 0; index < component.nodes.length; index++) {
        const pin = pins[index];
        if (!pin) continue;
        endpoints.push({
          component,
          pinIndex: index,
          node: component.nodes[index],
          column: pin.column,
          x: columnX(pin.column),
          y: pin.y,
          bank: component.isIc ? (index < component.nodes.length / 2 ? "top" : "bottom") : position.bank,
          railTerminal: pin.railTerminal === true,
        });
      }
    }

    const groups = new Map();
    for (const endpoint of endpoints) {
      const key = nodeKey(endpoint.node);
      if (!groups.has(key)) groups.set(key, { name: endpoint.node, endpoints: [] });
      groups.get(key).endpoints.push(endpoint);
    }
    const wireResult = wiringMode === "ratsnest"
      ? drawRatsnestWires(base, groups)
      : drawWires(base, groups, layout, components, positions);

    const overlay = svgElement("g", {});
    base.appendChild(overlay);
    const collisionIds = detectCollisions(components, positions, endpoints, wireResult.bridgePositions);
    for (const component of components) {
      if (!positions[component.id]) continue;
      drawComponent(
        overlay,
        component,
        positions[component.id],
        collisionIds.has(component.id),
        selectedComponentIds.has(component.id),
      );
    }
    for (const endpoint of endpoints) {
      overlay.appendChild(svgElement("circle", {
        cx: endpoint.x, cy: endpoint.y, r: 4.5,
        fill: colorFor(endpoint.node), stroke: "#fff", "stroke-width": 1.4,
      }));
    }

    if (collisionIds.size || wireResult.conflicts) {
      issues.push("Red-marked parts or wires have a placement conflict. Move them to clear the board.");
    }
    if (issues.length) showNotice([...new Set(issues)].join(" "));
    else hideNotice();
    document.getElementById("save-button").disabled = false;
    const modeStatus = document.getElementById("mode-status");
    const wiringLabel = wiringMode === "ratsnest" ? "Ratsnest (W)" : "Breadboard (W)";
    const colorLabel = printMode ? "Black and white (P)" : "Full color (P)";
    const modeLabel = `${wiringLabel} · ${colorLabel}`;
    if (modeStatus.textContent !== modeLabel) modeStatus.textContent = modeLabel;
  }

  function drawRail(parent, label, y, color) {
    parent.appendChild(svgElement("line", { x1: X_MIN, x2: X_MAX, y1: y, y2: y, class: "rail", stroke: color }));
    parent.appendChild(svgElement("text", { x: 17, y: y + 4, class: "rail-label", fill: color }, label));
    for (let i = 0; i < COLUMN_COUNT; i++) {
      const x = columnX(i);
      parent.appendChild(svgElement("circle", { cx: x, cy: y, r: 2.3, fill: "#fff", stroke: color, "stroke-width": 1 }));
    }
  }

  function drawBank(parent, rows, label) {
    parent.appendChild(svgElement("rect", { x: 26, y: rows[0] - 22, width: WIDTH - 52, height: rows[4] - rows[0] + 44, rx: 5, class: "bank" }));
    const rowNames = rows === TOP_ROWS ? ["A", "B", "C", "D", "E"] : ["F", "G", "H", "I", "J"];
    rows.forEach((y, index) => parent.appendChild(svgElement("text", {
      x: 43, y: y + 3, class: "row-label",
    }, rowNames[index])));
    for (let index = 0; index < COLUMN_COUNT; index++) {
      const x = columnX(index);
      for (const y of rows) {
        parent.appendChild(svgElement("circle", { cx: x, cy: y, r: 4.2, class: "hole" }));
      }
      parent.appendChild(svgElement("line", {
        x1: x, x2: x, y1: rows[0], y2: rows[4], class: "strip",
      }));
    }
    for (let index = 0; index < COLUMN_COUNT; index += 5) {
      parent.appendChild(svgElement("text", {
        x: columnX(index), y: rows[4] + 18, class: "column-label",
      }, String(index + 1)));
    }
    parent.appendChild(svgElement("text", { x: 38, y: rows[0] - 27, class: "bank-label" }, label));
  }

  function drawGap(parent) {
    parent.appendChild(svgElement("rect", { x: 26, y: 326, width: WIDTH - 52, height: 300, rx: 5, class: "gap" }));
    parent.appendChild(svgElement("line", { x1: 34, x2: WIDTH - 34, y1: 476, y2: 476, class: "gap-center" }));
    parent.appendChild(svgElement("text", { x: 42, y: 351, class: "bank-label" }, "ICs span the center gap"));
  }

  function pinLocations(component, position) {
    if (!component.isIc) {
      if (isVerticalRailPosition(component, position)) {
        const railIndex = railPinIndex(component);
        const railYPosition = railY(component, position);
        const gridY = edgeRowY(position.bank);
        return component.nodes.map((_, index) => ({
          column: position.column,
          y: index === railIndex ? railYPosition : gridY,
          railTerminal: index === railIndex,
        }));
      }
      const rows = position.bank === "top" ? TOP_ROWS : BOTTOM_ROWS;
      return pinOffsets(component, position.flipped).map(offset => ({
        column: position.column + offset,
        y: rows[position.row],
      }));
    }

    const half = component.nodes.length / 2;
    const upper = [];
    const lower = [];
    for (let index = 0; index < half; index++) {
      upper.push({ column: position.column + index, y: TOP_ROWS[4] });
      lower.push({ column: position.column + half - index - 1, y: BOTTOM_ROWS[0] });
    }
    return upper.concat(lower);
  }

  function drawWires(parent, groups, layout, components, positions) {
    const bankGroups = { top: [], bottom: [] };
    for (const group of groups.values()) {
      if (isRail(group.name)) {
        for (const endpoint of group.endpoints) drawRailContact(parent, endpoint, isRail(group.name));
        continue;
      }
      for (const bank of ["top", "bottom"]) {
        const endpoints = group.endpoints.filter(endpoint => endpoint.bank === bank);
        if (endpoints.length) bankGroups[bank].push({ group, endpoints });
      }
    }
    const bridgeNodes = new Set(
      [...groups.values()]
        .filter(group => !isRail(group.name) && new Set(group.endpoints.map(endpoint => endpoint.bank)).size === 2)
        .map(group => nodeKey(group.name))
    );
    const bridgePositions = {};
    const usedBridgeColumns = new Set();
    for (const group of groups.values()) {
      if (!bridgeNodes.has(nodeKey(group.name))) continue;
      const columns = group.endpoints.map(endpoint => endpoint.column);
      const savedColumn = layout.bridges[nodeKey(group.name)];
      const preferred = Number.isInteger(savedColumn) ? savedColumn : Math.round(average(columns));
      let column = preferred;
      function isAvailable(candidate) {
        return candidate >= 0 && candidate < COLUMN_COUNT && !usedBridgeColumns.has(candidate) &&
          ![...groups.values()].some(other =>
            nodeKey(other.name) !== nodeKey(group.name) &&
            other.endpoints.some(endpoint =>
              endpoint.column === candidate && (endpoint.bank === "top" || endpoint.bank === "bottom")
            )
          );
      }
      if (!Number.isInteger(savedColumn) && !isAvailable(column)) {
        for (let distance = 1; distance < COLUMN_COUNT; distance++) {
          const candidates = [preferred - distance, preferred + distance];
          const available = candidates.find(isAvailable);
          if (available !== undefined) {
            column = available;
            break;
          }
        }
      }
      bridgePositions[nodeKey(group.name)] = column;
      usedBridgeColumns.add(column);
    }
    const bridgeNodesByColumn = new Map();
    for (const [node, column] of Object.entries(bridgePositions)) {
      if (!bridgeNodesByColumn.has(column)) bridgeNodesByColumn.set(column, []);
      bridgeNodesByColumn.get(column).push(node);
    }
    const conflictingBridges = new Set(
      [...bridgeNodesByColumn.values()].filter(nodes => nodes.length > 1).flat()
    );
    const segments = [];
    const conflictingNodes = new Set();
    const laneFractions = [0.25, 0.35, 0.45, 0.55, 0.65, 0.75];

    function bodyBlocksHole(component, position, bank, rowIndex, column) {
      if (!position) return false;
      if (isVerticalRailPosition(component, position)) return false;
      if (component.isIc) {
        const half = component.nodes.length / 2;
        return bank === "top" && rowIndex === 4 && column >= position.column && column < position.column + half ||
          bank === "bottom" && rowIndex === 0 && column >= position.column && column < position.column + half;
      }
      if (position.bank !== bank || position.row !== rowIndex) return false;
      const halfWidth = componentBodyWidth(component) / 2;
      return Math.abs(column - position.column) * COLUMN_PITCH <= halfWidth;
    }

    function bodyIntersectsRange(component, position, bank, rowIndex, left, right) {
      if (!position || component.isIc || isVerticalRailPosition(component, position) ||
        position.bank !== bank || position.row !== rowIndex) return false;
      const halfWidth = componentBodyWidth(component) / 2 / COLUMN_PITCH;
      return position.column + halfWidth >= left && position.column - halfWidth <= right;
    }

    function bodyIntersectsDiagonal(component, position, bank, rowIndex, left, right) {
      if (!position || component.isIc || isVerticalRailPosition(component, position) ||
        position.bank !== bank || position.row !== rowIndex) return false;
      const halfWidth = componentBodyWidth(component) / 2 / COLUMN_PITCH;
      const diagonal = Math.min(0.35, (right - left) / 3);
      const bodyLeft = position.column - halfWidth;
      const bodyRight = position.column + halfWidth;
      return bodyLeft <= left + diagonal && left <= bodyRight ||
        bodyLeft <= right && right - diagonal <= bodyRight;
    }

    function laneCrossesBody(segment, rows, lane) {
      const startX = columnX(segment.leftColumn);
      const endX = columnX(segment.rightColumn);
      const diagonal = Math.min(COLUMN_PITCH * 0.35, (endX - startX) / 3);
      const horizontalStart = startX + diagonal;
      const horizontalEnd = endX - diagonal;
      return components.some(component => {
        const position = positions[component.id];
        if (!position || component.isIc || isVerticalRailPosition(component, position) ||
          position.bank !== segment.bank) return false;
        const halfWidth = componentBodyWidth(component) / 2 + 1.5;
        const halfHeight = 13 + 1.5;
        const centerY = rows[position.row];
        const bodyLeft = columnX(position.column) - halfWidth;
        const bodyRight = columnX(position.column) + halfWidth;
        return Math.abs(lane - centerY) <= halfHeight &&
          bodyLeft <= horizontalEnd && horizontalStart <= bodyRight;
      });
    }

    for (const bank of ["top", "bottom"]) {
      const rows = bank === "top" ? TOP_ROWS : BOTTOM_ROWS;
      for (const { group, endpoints } of bankGroups[bank]) {
        const bridgeColumn = bridgePositions[nodeKey(group.name)];
        const columns = [...new Set(endpoints.map(endpoint => endpoint.column))];
        if (bridgeColumn !== undefined) columns.push(bridgeColumn);
        const orderedColumns = [...new Set(columns)].sort((a, b) => a - b);
        if (orderedColumns.length < 2) continue;

        const endpointRowsByColumn = new Map();
        const endpointColumns = endpoints.map(endpoint => endpoint.column);
        let preferredEndpointRows = endpoints;
        if (bridgeColumn !== undefined && endpointColumns.length) {
          const minEndpointColumn = Math.min(...endpointColumns);
          const maxEndpointColumn = Math.max(...endpointColumns);
          if (bridgeColumn > maxEndpointColumn || bridgeColumn < minEndpointColumn) {
            const preferredColumn = bridgeColumn > maxEndpointColumn ? minEndpointColumn : maxEndpointColumn;
            preferredEndpointRows = endpoints.filter(endpoint => endpoint.column === preferredColumn);
          }
        }
        const groupEndpointRows = preferredEndpointRows.map(endpoint => rows.indexOf(endpoint.y)).filter(row => row >= 0);
        endpoints.forEach(endpoint => {
          const rowIndex = rows.indexOf(endpoint.y);
          if (rowIndex < 0) return;
          if (!endpointRowsByColumn.has(endpoint.column)) endpointRowsByColumn.set(endpoint.column, []);
          endpointRowsByColumn.get(endpoint.column).push(rowIndex);
        });
        for (let index = 0; index < orderedColumns.length - 1; index++) {
          const left = orderedColumns[index];
          const right = orderedColumns[index + 1];
          const localEndpointRows = [
            ...(endpointRowsByColumn.get(left) || []),
            ...(endpointRowsByColumn.get(right) || []),
          ];
          const routeRow = rows.map((_, rowIndex) => {
            const blockedHoles = [left, right].filter(column =>
              components.some(component => bodyBlocksHole(component, positions[component.id], bank, rowIndex, column))
            ).length;
            const blockedDiagonals = components.some(component =>
              bodyIntersectsDiagonal(component, positions[component.id], bank, rowIndex, left, right)
            ) ? 1 : 0;
            const bodyCount = components.filter(component =>
              bodyIntersectsRange(component, positions[component.id], bank, rowIndex, left, right)
            ).length;
            const groupEndpointDistance = groupEndpointRows.length
              ? Math.min(...groupEndpointRows.map(endpointRow => Math.abs(endpointRow - rowIndex)))
              : 0;
            const localEndpointDistance = localEndpointRows.length
              ? Math.min(...localEndpointRows.map(endpointRow => Math.abs(endpointRow - rowIndex)))
              : 0;
            return { rowIndex, blockedHoles, blockedDiagonals, bodyCount, groupEndpointDistance, localEndpointDistance };
          }).sort((a, b) =>
            a.blockedHoles - b.blockedHoles ||
            a.blockedDiagonals - b.blockedDiagonals ||
            a.groupEndpointDistance - b.groupEndpointDistance ||
            a.localEndpointDistance - b.localEndpointDistance ||
            a.bodyCount - b.bodyCount
          )[0];
          if (routeRow.blockedHoles || routeRow.blockedDiagonals) conflictingNodes.add(nodeKey(group.name));
          segments.push({
            node: nodeKey(group.name),
            name: group.name,
            leftColumn: left,
            rightColumn: right,
            bank,
            rowIndex: routeRow.rowIndex,
            lane: null,
          });
        }
      }
    }

    const assignedSegments = [];
    const laneAssignmentOrder = [...segments].sort((a, b) =>
      (b.rightColumn - b.leftColumn) - (a.rightColumn - a.leftColumn)
    );
    for (const segment of laneAssignmentOrder) {
      const rows = segment.bank === "top" ? TOP_ROWS : BOTTOM_ROWS;
      const options = [];
      const blockedOptions = [];
      for (let gap = 0; gap < rows.length - 1; gap++) {
        if (segment.rowIndex !== gap && segment.rowIndex !== gap + 1) continue;
        for (const fraction of laneFractions) {
          const lane = rows[gap] + (rows[gap + 1] - rows[gap]) * fraction;
          const overlaps = assignedSegments.filter(other =>
            other.bank === segment.bank &&
            other.node !== segment.node &&
            Math.abs(other.lane - lane) < 0.001 &&
            segment.leftColumn <= other.rightColumn &&
            other.leftColumn <= segment.rightColumn
          );
          const offset = segment.rowIndex === gap ? fraction : 1 - fraction;
          const option = { lane, offset, overlaps };
          if (laneCrossesBody(segment, rows, lane)) blockedOptions.push(option);
          else options.push(option);
        }
      }
      const availableOptions = options.length ? options : blockedOptions;
      if (!options.length) conflictingNodes.add(segment.node);
      availableOptions.forEach(option => {
        option.usage = assignedSegments.filter(other =>
          other.bank === segment.bank && Math.abs(other.lane - option.lane) < 0.001
        ).length;
      });
      availableOptions.sort((a, b) =>
        a.overlaps.length - b.overlaps.length ||
        a.usage - b.usage ||
        Math.abs(a.offset - 0.5) - Math.abs(b.offset - 0.5)
      );
      const chosen = availableOptions[0];
      segment.lane = chosen.lane;
      if (chosen.overlaps.length) {
        conflictingNodes.add(segment.node);
        chosen.overlaps.forEach(other => conflictingNodes.add(other.node));
      }
      assignedSegments.push(segment);
    }

    for (const segment of segments) {
      const conflicted = conflictingNodes.has(segment.node);
      const rows = segment.bank === "top" ? TOP_ROWS : BOTTOM_ROWS;
      const startX = columnX(segment.leftColumn);
      const endX = columnX(segment.rightColumn);
      const diagonal = Math.min(COLUMN_PITCH * 0.35, (endX - startX) / 3);
      parent.appendChild(svgElement("path", {
        d: `M ${startX} ${rows[segment.rowIndex]} L ${startX + diagonal} ${segment.lane} L ${endX - diagonal} ${segment.lane} L ${endX} ${rows[segment.rowIndex]}`,
        class: conflicted ? "wire wire-conflict" : "wire",
        stroke: conflicted ? "#c52b34" : colorFor(segment.name),
        "data-node": segment.name,
      }));
    }

    for (const group of groups.values()) {
      if (isRail(group.name)) continue;
      const halves = new Set(group.endpoints.map(endpoint => endpoint.bank));
      if (halves.size !== 2) continue;
      const key = nodeKey(group.name);
      const bridgeX = columnX(bridgePositions[key]);
      const conflicted = conflictingBridges.has(key) || conflictingNodes.has(key);
      const color = conflicted ? "#c52b34" : colorFor(group.name);
      parent.appendChild(svgElement("line", {
        x1: bridgeX, x2: bridgeX, y1: TOP_ROWS[4], y2: BOTTOM_ROWS[0],
        class: conflicted ? "wire bridge-wire wire-conflict" : "wire bridge-wire", stroke: color,
        "data-bridge": key, "data-node": group.name,
      }));
      parent.appendChild(svgElement("circle", {
        cx: bridgeX, cy: 476, r: 8, class: "bridge-handle", "data-bridge": key, "data-node": group.name,
      }));
      parent.appendChild(svgElement("text", {
        x: bridgeX + 12, y: 480, class: "bridge-label", "data-bridge": key,
      }, group.name));
    }
    return {
      conflicts: conflictingNodes.size > 0 || conflictingBridges.size > 0,
      bridgePositions,
    };
  }

  function drawRatsnestWires(parent, groups) {
    for (const group of groups.values()) {
      const rail = isRail(group.name);
      if (rail) {
        for (const endpoint of group.endpoints) {
          const railY = rail === "VCC" ? 46
            : rail === "VEE" ? 912
              : endpoint.bank === "top" ? 83 : 875;
          parent.appendChild(svgElement("line", {
            x1: endpoint.x,
            x2: endpoint.x,
            y1: endpoint.y,
            y2: railY,
            class: "wire ratsnest-wire",
            stroke: colorFor(group.name),
            "data-node": group.name,
          }));
          drawRailContact(parent, endpoint, rail);
        }
        continue;
      }

      const endpoints = group.endpoints;
      if (endpoints.length < 2) continue;

      const connected = new Set([0]);
      while (connected.size < endpoints.length) {
        let closest = null;
        for (const from of connected) {
          for (let to = 0; to < endpoints.length; to++) {
            if (connected.has(to)) continue;
            const dx = endpoints[from].x - endpoints[to].x;
            const dy = endpoints[from].y - endpoints[to].y;
            const distance = dx * dx + dy * dy;
            if (!closest || distance < closest.distance) closest = { from, to, distance };
          }
        }
        const start = endpoints[closest.from];
        const end = endpoints[closest.to];
        parent.appendChild(svgElement("line", {
          x1: start.x,
          y1: start.y,
          x2: end.x,
          y2: end.y,
          class: "wire ratsnest-wire",
          stroke: colorFor(group.name),
          "data-node": group.name,
        }));
        connected.add(closest.to);
      }
    }
    return { conflicts: false, bridgePositions: {} };
  }

  function drawRailContact(parent, endpoint, rail) {
    const y = rail === "VCC" ? 46 : rail === "VEE" ? 912 : endpoint.bank === "top" ? 83 : 875;
    parent.appendChild(svgElement("circle", {
      cx: endpoint.x, cy: y, r: 4.5, class: "rail-contact",
      fill: colorFor(endpoint.node),
    }));
  }

  function drawComponent(parent, component, position, collision, selected) {
    const vertical = isVerticalRailPosition(component, position);
    const centerX = component.isIc
      ? columnX(position.column + (component.nodes.length / 2 - 1) / 2)
      : columnX(position.column);
    const centerY = componentCenterY(component, position);
    const group = svgElement("g", {
      class: `component${component.isIc ? " ic" : ""}${vertical ? " vertical" : ""}${collision ? " collision" : ""}${selected ? " selected" : ""}`,
      transform: `translate(${centerX} ${centerY})`,
      "data-component": component.id,
      "aria-label": `${component.reference} ${component.value}`,
    });
    const interactionHelp = component.isIc ? "" : vertical
      ? "; drag to reposition and press R to toggle orientation"
      : `; drag to reposition${canRotateVertically(component) ? ", press X to flip, or R to rotate" : " and press X to flip"}`;
    group.appendChild(svgElement("title", {}, `${component.reference}: ${component.value}${interactionHelp}`));
    if (component.isIc) {
      const half = component.nodes.length / 2;
      const width = Math.max(100, (half - 1) * COLUMN_PITCH + 68);
      for (let index = 0; index < half; index++) {
        const x = (index - (half - 1) / 2) * COLUMN_PITCH;
        group.appendChild(svgElement("line", {
          x1: x, x2: x, y1: TOP_ROWS[4] - centerY, y2: -84, class: "ic-lead",
        }));
        group.appendChild(svgElement("line", {
          x1: x, x2: x, y1: 84, y2: BOTTOM_ROWS[0] - centerY, class: "ic-lead",
        }));
      }
      group.appendChild(svgElement("rect", { x: -width / 2, y: -84, width, height: 168, rx: 7, class: "ic-body" }));
      group.appendChild(svgElement("path", { d: `M -18 -84 Q -18 -62 0 -62 Q 18 -62 18 -84`, class: "ic-notch" }));
      group.appendChild(svgElement("text", { x: 0, y: -6, class: "component-ref" }, component.reference));
      group.appendChild(svgElement("text", { x: 0, y: 15, class: "component-value" }, component.value));
      group.appendChild(svgElement("text", { x: -width / 2 + 5, y: -91, class: "pin-number" }, "1"));
      group.appendChild(svgElement("text", { x: width / 2 - 5, y: 105, class: "pin-number" }, String(component.nodes.length / 2 + 1)));
    } else {
      if (vertical) {
        const railIndex = railPinIndex(component);
        const railOffset = railY(component, position) - centerY;
        const gridOffset = edgeRowY(position.bank) - centerY;
        group.appendChild(svgElement("line", {
          x1: 0, x2: 0, y1: railOffset, y2: gridOffset, class: "part-lead",
        }));
        group.appendChild(svgElement("rect", {
          x: -13, y: -25, width: 26, height: 50, rx: component.kind === "c" ? 2 : 5,
          class: "part-body",
        }));
        group.appendChild(svgElement("text", { x: 0, y: -6, class: "component-ref" }, component.reference));
        group.appendChild(svgElement("text", { x: 0, y: 10, class: "component-value" }, component.value));
        component.nodes.forEach((_, index) => {
          const y = index === railIndex ? railOffset : gridOffset;
          group.appendChild(svgElement("text", { x: 15, y: y + 3, class: "pin-number" }, String(index + 1)));
        });
      } else {
        const width = componentBodyWidth(component);
        const offsets = pinOffsets(component, position.flipped);
        const leadReach = Math.max(...offsets.map(Math.abs)) * COLUMN_PITCH;
        group.appendChild(svgElement("line", { x1: -leadReach, x2: leadReach, y1: 0, y2: 0, class: "part-lead" }));
        group.appendChild(svgElement("rect", {
          x: -width / 2, y: -13, width, height: 26, rx: component.kind === "c" ? 2 : 5,
          class: "part-body",
        }));
        group.appendChild(svgElement("text", { x: 0, y: -2, class: "component-ref" }, component.reference));
        group.appendChild(svgElement("text", { x: 0, y: 10, class: "component-value" }, component.value));
        group.appendChild(svgElement("text", { x: offsets[0] * COLUMN_PITCH, y: -17, class: "pin-number" }, "1"));
        if (component.nodes.length > 1) {
          group.appendChild(svgElement("text", {
            x: offsets[offsets.length - 1] * COLUMN_PITCH,
            y: -17,
            class: "pin-number",
          }, String(component.nodes.length)));
        }
      }
    }
    parent.appendChild(group);
  }

  function detectCollisions(components, positions, endpoints, bridgePositions) {
    const collisions = new Set();
    const placed = components.filter(component => positions[component.id]);
    for (const component of placed) {
      const position = positions[component.id];
      const vertical = isVerticalRailPosition(component, position);
      const start = position.column;
      const end = component.isIc
        ? position.column + component.nodes.length / 2 - 1
        : vertical
          ? position.column
        : position.column + Math.max(...pinOffsets(component));
      const first = component.isIc
        ? start
        : vertical
          ? position.column
        : position.column + Math.min(...pinOffsets(component));
      if (first < 0 || end >= COLUMN_COUNT) collisions.add(component.id);
    }
    for (let left = 0; left < placed.length; left++) {
      for (let right = left + 1; right < placed.length; right++) {
        const a = placed[left];
        const b = placed[right];
        if (a.isIc !== b.isIc) continue;
        const pa = positions[a.id];
        const pb = positions[b.id];
        const aVertical = isVerticalRailPosition(a, pa);
        const bVertical = isVerticalRailPosition(b, pb);
        const aWidth = a.isIc ? a.nodes.length / 2 : pinOffsets(a).length === 4 ? 4 : 2;
        const bWidth = b.isIc ? b.nodes.length / 2 : pinOffsets(b).length === 4 ? 4 : 2;
        const aLeft = a.isIc ? pa.column : aVertical ? pa.column : pa.column + Math.min(...pinOffsets(a));
        const aRight = a.isIc ? pa.column + aWidth - 1 : aVertical ? pa.column : pa.column + Math.max(...pinOffsets(a));
        const bLeft = b.isIc ? pb.column : bVertical ? pb.column : pb.column + Math.min(...pinOffsets(b));
        const bRight = b.isIc ? pb.column + bWidth - 1 : bVertical ? pb.column : pb.column + Math.max(...pinOffsets(b));
        const aRow = aVertical ? (pa.bank === "top" ? 0 : 4) : pa.row;
        const bRow = bVertical ? (pb.bank === "top" ? 0 : 4) : pb.row;
        const sameRow = a.isIc || (pa.bank === pb.bank && aRow === bRow);
        if (sameRow && aLeft <= bRight && bLeft <= aRight) {
          collisions.add(a.id);
          collisions.add(b.id);
        }
      }
    }
    const holes = new Map();
    for (const endpoint of endpoints) {
      if (endpoint.railTerminal) continue;
      const key = `${endpoint.bank}:${endpoint.column}`;
      if (!holes.has(key)) holes.set(key, []);
      holes.get(key).push(endpoint);
    }
    for (const [node, column] of Object.entries(bridgePositions)) {
      for (const bank of ["top", "bottom"]) {
        const key = `${bank}:${column}`;
        if (!holes.has(key)) holes.set(key, []);
        holes.get(key).push({ node, bridge: true });
      }
    }
    for (const occupants of holes.values()) {
      if (new Set(occupants.map(endpoint => nodeKey(endpoint.node))).size > 1) {
        for (const endpoint of occupants) {
          if (endpoint.component) collisions.add(endpoint.component.id);
          if (endpoint.bridge) {
            for (const other of endpoints) {
              if (nodeKey(other.node) === endpoint.node) collisions.add(other.component.id);
            }
          }
        }
      }
    }
    return collisions;
  }

  function colorFor(node) {
    const rail = isRail(node);
    if (rail === "VCC") return "#d84a4a";
    if (rail === "VEE") return "#3572c6";
    if (rail === "GND") return "#424a52";
    let hash = 0;
    for (const char of node.toLowerCase()) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    return COLORS[hash % COLORS.length];
  }

  function average(numbers) {
    return numbers.reduce((sum, number) => sum + number, 0) / numbers.length;
  }

  function showNotice(message) {
    const notice = document.getElementById("notice");
    notice.textContent = message;
    notice.hidden = false;
    notice.classList.toggle(
      "error",
      Boolean(root.Breadboard.state && root.Breadboard.state.parseErrors.length > 0)
    );
  }

  function hideNotice() {
    const notice = document.getElementById("notice");
    notice.hidden = true;
    notice.textContent = "";
    notice.classList.remove("error");
  }

  function boardPoint(event) {
    const board = document.getElementById("board");
    const point = board.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(board.getScreenCTM().inverse());
  }

  function enableDragging() {
    const board = document.getElementById("board");
    let drag = null;
    function selectComponent(id, shiftKey) {
      if (id === null) {
        if (!shiftKey) selectedComponentIds.clear();
      } else if (shiftKey) {
        if (selectedComponentIds.has(id)) selectedComponentIds.delete(id);
        else selectedComponentIds.add(id);
      } else if (!selectedComponentIds.has(id)) {
        selectedComponentIds = new Set([id]);
      }
      for (const element of board.querySelectorAll("[data-component]")) {
        element.classList.toggle("selected", selectedComponentIds.has(element.dataset.component));
      }
    }

    board.addEventListener("pointerdown", event => {
      const component = event.target.closest("[data-component]");
      const bridge = event.target.closest("[data-bridge]");
      if (!component && !bridge) {
        selectComponent(null, event.shiftKey);
        return;
      }
      selectComponent(component ? component.dataset.component : null, event.shiftKey);
      const point = boardPoint(event);
      if (component) {
        const item = root.Breadboard.state.layout.components[component.dataset.component];
        const definition = root.Breadboard.state.components.find(entry => entry.id === component.dataset.component);
        const anchorX = definition.isIc
          ? columnX(item.column + (definition.nodes.length / 2 - 1) / 2)
          : columnX(item.column);
        const anchorY = componentCenterY(definition, item);
        drag = {
          type: "component",
          id: component.dataset.component,
          dx: anchorX - point.x,
          dy: anchorY - point.y,
        };
      } else {
        drag = { type: "bridge", id: bridge.dataset.bridge };
      }
      board.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    board.addEventListener("pointermove", event => {
      if (!drag) return;
      const point = boardPoint(event);
      if (drag.type === "component") {
        const component = root.Breadboard.state.components.find(item => item.id === drag.id);
        const position = root.Breadboard.state.layout.components[drag.id];
        if (component.isIc) {
          const half = component.nodes.length / 2;
          const centerColumn = (point.x + drag.dx - X_MIN) / COLUMN_PITCH;
          position.column = Math.max(0, Math.min(COLUMN_COUNT - half, Math.round(centerColumn - (half - 1) / 2)));
        } else if (isVerticalRailPosition(component, position)) {
          position.column = Math.max(0, Math.min(COLUMN_COUNT - 1, columnAt(point.x + drag.dx)));
          position.bank = point.y + drag.dy < 476 ? "top" : "bottom";
        } else {
          const offsets = pinOffsets(component);
          position.column = clampStandardColumn(component, columnAt(point.x + drag.dx));
          const bank = point.y + drag.dy < 476 ? "top" : "bottom";
          const rows = bank === "top" ? TOP_ROWS : BOTTOM_ROWS;
          position.bank = bank;
          position.row = nearestIndex(point.y + drag.dy, rows);
          if (position.column + Math.max(...offsets) >= COLUMN_COUNT) {
            position.column = clampStandardColumn(component, COLUMN_COUNT - 1 - Math.max(...offsets));
          }
        }
      } else {
        root.Breadboard.state.layout.bridges[drag.id] = columnAt(point.x);
      }
      draw();
    });
    board.addEventListener("pointerup", () => { drag = null; });
    board.addEventListener("pointercancel", () => { drag = null; });
    document.addEventListener("keydown", event => {
      if (event.altKey || event.ctrlKey || event.metaKey ||
        (event.target.closest && event.target.closest("input, textarea, select, [contenteditable='true']"))) return;

      const key = event.key.toLowerCase();
      if (key === "w") {
        if (event.repeat) return;
        wiringMode = wiringMode === "breadboard" ? "ratsnest" : "breadboard";
        event.preventDefault();
        draw();
      } else if (key === "p") {
        if (event.repeat) return;
        if (event.target.closest && event.target.closest("button")) return;
        printMode = !printMode;
        event.preventDefault();
        draw();
      } else if (key === "x") {
        if (event.repeat) return;
        if (event.target.closest && event.target.closest("button")) return;
        const selected = root.Breadboard.state.components.filter(item =>
          !item.isIc && selectedComponentIds.has(item.id) &&
          !isVerticalRailPosition(item, root.Breadboard.state.layout.components[item.id])
        );
        if (!selected.length) return;
        for (const component of selected) {
          const position = root.Breadboard.state.layout.components[component.id];
          position.flipped = !position.flipped;
        }
        event.preventDefault();
        draw();
      } else if (key === "r") {
        if (event.repeat) return;
        if (event.target.closest && event.target.closest("button")) return;
        const selected = root.Breadboard.state.components.filter(item =>
          canRotateVertically(item) && selectedComponentIds.has(item.id)
        );
        if (!selected.length) return;
        for (const component of selected) {
          const position = root.Breadboard.state.layout.components[component.id];
          const railOffset = pinOffsets(component, position.flipped)[railPinIndex(component)];
          if (isVerticalRailPosition(component, position)) {
            position.column = clampStandardColumn(component, position.column - railOffset);
            position.vertical = false;
          } else {
            position.column = Math.max(0, Math.min(COLUMN_COUNT - 1, position.column + railOffset));
            position.vertical = true;
          }
        }
        event.preventDefault();
        draw();
      } else if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        if (!selectedComponentIds.size) return;
        const movement = {
          ArrowLeft: [-1, 0],
          ArrowRight: [1, 0],
          ArrowUp: [0, -1],
          ArrowDown: [0, 1],
        }[event.key];
        for (const id of selectedComponentIds) {
          const component = root.Breadboard.state.components.find(item => item.id === id);
          const position = root.Breadboard.state.layout.components[id];
          const vertical = isVerticalRailPosition(component, position);
          if (movement[0] !== 0) {
            if (component.isIc) {
              const maxStart = Math.max(0, COLUMN_COUNT - component.nodes.length / 2);
              position.column = Math.max(0, Math.min(maxStart, position.column + movement[0]));
            } else if (vertical) {
              position.column = Math.max(0, Math.min(COLUMN_COUNT - 1, position.column + movement[0]));
            } else {
              position.column = clampStandardColumn(component, position.column + movement[0]);
            }
          } else if (!component.isIc && !vertical) {
            position.row = Math.max(0, Math.min(4, position.row + movement[1]));
          }
        }
        event.preventDefault();
        draw();
      }
    });
  }

  function nearestIndex(value, choices) {
    return choices.reduce((bestIndex, item, index) =>
      Math.abs(item - value) < Math.abs(choices[bestIndex] - value) ? index : bestIndex, 0);
  }

  async function saveLayout() {
    const button = document.getElementById("save-button");
    const status = document.getElementById("save-status");
    button.disabled = true;
    status.textContent = "Saving…";
    try {
      const response = await fetch("/api/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(root.Breadboard.state.layout),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      status.textContent = `Saved ${result.file}`;
    } catch (error) {
      status.textContent = `Save failed: ${error.message}`;
      showNotice(`Could not save layout: ${error.message}`);
    } finally {
      button.disabled = false;
    }
  }

  async function initialize() {
    const status = document.getElementById("save-status");
    try {
      const response = await fetch("/api/state");
      const state = await response.json();
      if (!response.ok) throw new Error(state.error || `HTTP ${response.status}`);
      const parsed = parseCircuit(state.circuitText, state.subcircuits);
      const defaults = defaultLayout(parsed.components);
      const layout = migrateLayout(state.layout, parsed.components, defaults);
      root.Breadboard.state = {
        components: parsed.components,
        parseErrors: parsed.errors,
        layout,
      };
      document.getElementById("circuit-name").textContent = state.circuitName;
      document.getElementById("save-button").addEventListener("click", saveLayout);
      enableDragging();
      draw();
      status.textContent = state.layout.version === 1 || state.layout.version === 2
        ? "Loaded saved layout"
        : "Default placement";
    } catch (error) {
      status.textContent = "Could not load circuit";
      showNotice(`Could not load the circuit: ${error.message}`);
      document.getElementById("notice").classList.add("error");
    }
  }

  root.Breadboard = { parseCircuit, defaultLayout, draw, state: null };
  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", initialize);
  }
})(typeof window === "undefined" ? globalThis : window);
