import {
  Direction,
  GameMode,
  ItemStack,
  system,
  world,
} from "@minecraft/server";
import { spawnSimulatedPlayer } from "@minecraft/server-gametest";
import { OBJECTIVE_SELECTOR_V0 } from "./policy_weights.js";

const COMMAND = "archie:start";
const BLUEPRINT_COMMAND = "archie:blueprint";
const STRUCTURE_COMMAND = "archie:structure";
const VISION_ON_COMMAND = "archie:vision_on";
const VISION_OFF_COMMAND = "archie:vision_off";
const EXTERNAL_ON_COMMAND = "archie:external_on";
const EXTERNAL_OFF_COMMAND = "archie:external_off";
const EXTERNAL_ACTION_COMMAND = "archie:policy_action";
const BLOCK_TYPE = "minecraft:stone";
const MAX_ATTEMPTS = 3;
const VERIFY_TICKS = 10;
const AIM_SETTLE_TICKS = 8;
const MOVE_TIMEOUT_TICKS = 40;
const MOVEMENT_POLL_TICKS = 2;
const INSPECTION_HOLD_TICKS = 20;
const VISION_SETTLE_TICKS = 240;
const POLICY_TIMEOUT_TICKS = 100;
const POLICY_WIDTH = 5;
const COMPLETE_ACTION = 25;

let activePlayer;
let visionPlayer;
let visionCameraRun;
let externalToken;
let pendingPolicy;
let episodeCounter = 0;
const DEFAULT_BLUEPRINT = Object.freeze({
  mode: "planar",
  name: "3x3-wall",
  block: BLOCK_TYPE,
  rows: ["111", "111", "111"],
});
let selectedBlueprint = DEFAULT_BLUEPRINT;

function parseBlueprint(message) {
  let value;
  try {
    value = JSON.parse(message);
  } catch {
    throw new Error("blueprint must be valid JSON");
  }
  const name = typeof value.name === "string" ? value.name.trim() : "";
  const block = typeof value.block === "string" ? value.block.trim() : "";
  const rows = value.rows;
  if (!name || name.length > 48) throw new Error("name must contain 1-48 characters");
  if (!block.startsWith("minecraft:")) throw new Error("block must be a minecraft:* identifier");
  if (!Array.isArray(rows) || rows.length < 1 || rows.length > POLICY_WIDTH) {
    throw new Error("rows must contain 1-5 bottom-to-top strings");
  }
  const width = typeof rows[0] === "string" ? rows[0].length : 0;
  if (width < 1 || width > POLICY_WIDTH) throw new Error("row width must be 1-5 cells");
  if (rows.some((row) => typeof row !== "string" || row.length !== width || !/^[01]+$/.test(row))) {
    throw new Error("rows must have equal width and contain only 0 or 1");
  }
  let blocks = 0;
  for (let y = 0; y < rows.length; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (rows[y][x] !== "1") continue;
      blocks += 1;
      if (y > 0 && rows[y - 1][x] !== "1") {
        throw new Error(`unsupported cell at row ${y + 1}, column ${x + 1}`);
      }
    }
  }
  if (blocks === 0) throw new Error("blueprint must contain at least one block");
  return Object.freeze({ mode: "planar", name, block, rows: rows.slice() });
}

function parseStructure(message) {
  let value;
  try {
    value = JSON.parse(message);
  } catch {
    throw new Error("structure must be valid JSON");
  }
  const name = typeof value.name === "string" ? value.name.trim() : "";
  if (!name || name.length > 48) throw new Error("name must contain 1-48 characters");
  if (!Array.isArray(value.palette) || value.palette.length < 1 || value.palette.length > 9) {
    throw new Error("palette must contain 1-9 blocks");
  }
  const palette = value.palette.map((entry) => {
    if (!entry || typeof entry.name !== "string" || !entry.name.startsWith("minecraft:")) {
      throw new Error("every palette entry needs a minecraft:* name");
    }
    if (entry.states && Object.keys(entry.states).length > 0) {
      throw new Error("block states are not physically supported yet");
    }
    return { name: entry.name, states: {} };
  });
  if (!Array.isArray(value.cells) || value.cells.length < 1 || value.cells.length > 64) {
    throw new Error("cells must contain 1-64 blocks");
  }
  const occupied = new Set();
  const cells = value.cells.map((cell) => {
    if (!Array.isArray(cell) || cell.length !== 4 || cell.some((part) => !Number.isInteger(part))) {
      throw new Error("every cell must be [x,y,z,paletteIndex]");
    }
    const [x, y, z, paletteIndex] = cell;
    if (x < 0 || y < 0 || z < 0 || x > 4 || y > 4 || z > 4) {
      throw new Error("cell coordinates must fit within 5×5×5");
    }
    if (paletteIndex < 0 || paletteIndex >= palette.length) throw new Error("palette index is out of range");
    const key = `${x},${y},${z}`;
    if (occupied.has(key)) throw new Error(`duplicate cell at ${key}`);
    occupied.add(key);
    return [x, y, z, paletteIndex];
  });
  for (const [x, y, z] of cells) {
    if (y > 0 && !occupied.has(`${x},${y - 1},${z}`)) {
      throw new Error(`unsupported cell at ${x},${y},${z}`);
    }
  }
  // Complete one horizontal placement ray at a time: floor-by-floor,
  // lane-by-lane, far-to-near. Archie can keep nearly the same viewing angle
  // and click successive blocks toward its construction vantage.
  cells.sort((a, b) => a[1] - b[1] || a[0] - b[0] || b[2] - a[2]);
  const strategy = value.strategy;
  if (!strategy || !["ground", "jump", "existing_support", "scaffold"].includes(strategy.access)) {
    throw new Error("strategy access method is missing or unsupported");
  }
  if (!["north", "east", "south", "west"].includes(strategy.approach)) {
    throw new Error("strategy approach is missing or unsupported");
  }
  if (!Number.isInteger(strategy.scaffold_blocks) || strategy.scaffold_blocks < 0) {
    throw new Error("strategy scaffold count is invalid");
  }
  return Object.freeze({ mode: "spatial", name, palette, cells, strategy: Object.freeze(strategy) });
}

function stopVisionCamera(requestingPlayer) {
  if (visionCameraRun !== undefined) {
    system.clearRun(visionCameraRun);
    visionCameraRun = undefined;
  }
  const playerToClear = requestingPlayer ?? visionPlayer;
  if (playerToClear) {
    try {
      playerToClear.runCommand("camera @s clear");
      playerToClear.runCommand("hud @s reset");
      playerToClear.sendMessage("§5[Archie]§r Vision camera disabled.");
    } catch {
      // The viewing player may have disconnected.
    }
  }
  visionPlayer = undefined;
}

function startVisionCamera() {
  if (!visionPlayer || !activePlayer || visionCameraRun !== undefined) return;
  visionCameraRun = system.runInterval(() => {
    if (!visionPlayer || !activePlayer) return;
    try {
      const location = activePlayer.location;
      const rotation = activePlayer.getRotation();
      visionPlayer.runCommand(
        `camera @s set minecraft:free pos ${location.x} ${location.y + 1.62} ${location.z} rot ${rotation.x} ${rotation.y}`,
      );
    } catch (error) {
      emit("EPISODE_FAILED", { stage: "vision_camera", error: String(error) });
      stopVisionCamera();
    }
  }, 2);
}

function dense(input, layer, relu) {
  return layer.weights.map((row, outputIndex) => {
    let value = layer.bias[outputIndex];
    for (let inputIndex = 0; inputIndex < input.length; inputIndex += 1) {
      value += row[inputIndex] * input[inputIndex];
    }
    return relu ? Math.max(0, value) : value;
  });
}

function selectNeuralObjective(blueprint, built) {
  let values = blueprint.concat(built);
  values = dense(values, OBJECTIVE_SELECTOR_V0.layers[0], true);
  values = dense(values, OBJECTIVE_SELECTOR_V0.layers[1], true);
  const logits = dense(values, OBJECTIVE_SELECTOR_V0.layers[2], false);
  const valid = [];
  for (let index = 0; index < 25; index += 1) {
    if (blueprint[index] && !built[index] && (index < POLICY_WIDTH || built[index - POLICY_WIDTH])) {
      valid.push(index);
    }
  }
  if (valid.length === 0) return { action: COMPLETE_ACTION, logits, valid: [COMPLETE_ACTION] };
  let action = valid[0];
  for (const candidate of valid.slice(1)) {
    if (logits[candidate] > logits[action]) action = candidate;
  }
  return { action, logits, valid };
}

function rejectExternalDecision(reason, payload = {}) {
  emit("POLICY_DECISION_REJECTED", { reason, ...payload });
}

function requestExternalDecision(episode, revision, blueprint, built, fallback, callback) {
  if (pendingPolicy) {
    system.clearRun(pendingPolicy.timeout);
    rejectExternalDecision("superseded", { episode: pendingPolicy.episode, revision: pendingPolicy.revision });
  }
  const request = {
    episode,
    revision,
    valid: fallback.valid,
    fallback_action: fallback.action,
    callback,
  };
  request.timeout = system.runTimeout(() => {
    if (pendingPolicy !== request) return;
    pendingPolicy = undefined;
    emit("POLICY_FALLBACK_USED", {
      episode,
      revision,
      action: fallback.action,
      reason: "external inference timeout",
    });
    callback(fallback.action, "objective-selector-v0-fallback");
  }, POLICY_TIMEOUT_TICKS);
  pendingPolicy = request;
  emit("POLICY_DECISION_REQUESTED", {
    episode,
    revision,
    blueprint,
    built,
    valid_actions: fallback.valid,
    fallback_action: fallback.action,
  });
}

function blockPosition(location) {
  return {
    x: Math.floor(location.x),
    y: Math.floor(location.y),
    z: Math.floor(location.z),
  };
}

function add(position, x, y, z) {
  return { x: position.x + x, y: position.y + y, z: position.z + z };
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

function placementDecision(decision, reason, target, attempt = 0) {
  emit("PLACEMENT_DECISION", { decision, reason, target, attempt });
}

function emit(eventType, payload = {}) {
  const event = JSON.stringify({
    event_type: eventType,
    timestamp_ticks: system.currentTick,
    payload,
  });
  console.info(`[ArchieTelemetry] ${event}`);
  // Preview buffers content-log writes in chunks. A padded boundary after
  // decision/state/terminal events keeps the external live debugger current.
  if (
    eventType === "OBJECTIVE_SELECTED"
    || eventType === "STATE_UPDATED"
    || eventType === "POLICY_DECISION_REQUESTED"
    || eventType === "POLICY_DECISION_APPLIED"
    || eventType === "POLICY_DECISION_REJECTED"
    || eventType === "POLICY_FALLBACK_USED"
    || eventType === "VIEWPOINT_SELECTED"
    || eventType === "VISUAL_CHECK"
    || eventType === "EPISODE_COMPLETED"
    || eventType === "EPISODE_FAILED"
  ) {
    console.info(`[ArchieTelemetryFlush] ${".".repeat(4096)}`);
  }

  // Do not leak privileged progress labels into pixels retained for vision
  // training. Structured telemetry remains available out of band.
  if (visionPlayer) return;

  if (eventType === "EPISODE_STARTED") {
    world.sendMessage(`§5[Archie]§r Starting ${payload.blueprint} with §dObjective Selector V0§r (${payload.total_blocks} blocks).`);
  } else if (eventType === "STATE_UPDATED" && payload.correct > 0) {
    const percent = Math.round(payload.completion * 100);
    world.sendMessage(`§5[Archie]§r Progress: ${payload.correct}/${payload.correct + payload.missing} blocks (${percent}%).`);
  } else if (eventType === "FAULT_DETECTED") {
    world.sendMessage(`§6[Archie] Retrying block; attempt ${payload.next_attempt}/${MAX_ATTEMPTS}.§r`);
  } else if (eventType === "EPISODE_COMPLETED") {
    world.sendMessage(`§a[Archie] Complete: ${payload.correct_blocks}/${payload.correct_blocks + payload.missing_blocks} blocks verified.§r`);
  } else if (eventType === "EPISODE_FAILED") {
    const correct = payload.correct_blocks ?? 0;
    const missing = payload.missing_blocks ?? "?";
    world.sendMessage(`§c[Archie] Build stopped: ${correct} correct, ${missing} missing.§r`);
  }
}

function disconnectActivePlayer() {
  if (!activePlayer) return;
  try {
    activePlayer.disconnect();
  } catch {
    // It may already have been removed by a reload or previous failed run.
  }
  activePlayer = undefined;
}

function startPhysicalBuild(source) {
  disconnectActivePlayer();
  if (pendingPolicy) {
    system.clearRun(pendingPolicy.timeout);
    pendingPolicy = undefined;
  }

  const episode = `${system.currentTick}-${++episodeCounter}`;
  let stateRevision = 0;
  let lastInspectedLayer = -1;
  const blueprintDefinition = selectedBlueprint;
  const spatial = blueprintDefinition.mode === "spatial";
  const blueprintRows = spatial ? null : blueprintDefinition.rows;
  const blueprintWidth = spatial
    ? Math.max(...blueprintDefinition.cells.map((cell) => cell[0])) + 1
    : blueprintRows[0].length;
  const blueprintBlock = spatial ? null : blueprintDefinition.block;
  const arrivalThreshold = spatial ? 1.25 : 2.25;

  const dimension = source.dimension;
  // Keep the observing player outside Archie's spawn-to-wall navigation path.
  const origin = add(blockPosition(source.location), 4, 0, 0);
  const start = add(origin, 1, 0, 4);
  const targets = new Map();
  if (spatial) {
    blueprintDefinition.cells.forEach(([x, y, depth, paletteIndex], action) => {
      const lateral = x - Math.floor(blueprintWidth / 2);
      const target = add(origin, 2 + depth, y, lateral);
      // A compact structure can be reached from one central vantage. Looking
      // at each support supplies the placement angle without needless walking.
      const vantageLateral = blueprintWidth <= 3 ? 0 : lateral;
      targets.set(action, {
        target,
        support: add(target, 0, -1, 0),
        // Stay two blocks clear of the front face. At one block away the
        // simulated player's hitbox can overlap the next placement volume.
        stand: add(origin, 0, 0, vantageLateral),
        block: blueprintDefinition.palette[paletteIndex].name,
        slot: paletteIndex,
        relativeX: x,
        relativeY: y,
        relativeDepth: depth,
      });
    });
  } else {
    for (let y = 0; y < blueprintRows.length; y += 1) {
      for (let x = 0; x < blueprintWidth; x += 1) {
        if (blueprintRows[y][x] !== "1") continue;
        const z = x - Math.floor(blueprintWidth / 2);
        targets.set(y * POLICY_WIDTH + x, {
          target: add(origin, 2, y, z),
          support: add(origin, 2, y - 1, z),
          stand: add(origin, 1, 0, z),
          block: blueprintBlock,
          slot: 0,
          relativeX: x,
          relativeY: y,
          relativeDepth: 0,
        });
      }
    }
  }

  // Direct editing is restricted to the repeatable test fixture. The target
  // structure itself is always placed by the simulated player's inventory use.
  for (const task of targets.values()) {
    if (task.relativeY === 0) dimension.getBlock(task.support)?.setType("minecraft:bedrock");
    dimension.getBlock(task.target)?.setType("minecraft:air");
    dimension.getBlock(task.stand)?.setType("minecraft:air");
    dimension.getBlock(add(task.stand, 0, 1, 0))?.setType("minecraft:air");
  }
  dimension.getBlock(start)?.setType("minecraft:air");

  emit("EPISODE_STARTED", {
    origin,
    blueprint: blueprintDefinition.name,
    block: spatial ? "palette" : blueprintBlock,
    total_blocks: targets.size,
    policy: spatial ? "spatial-blueprint-planner-v0" : "objective-selector-v0",
    episode,
    vision_capture: visionPlayer !== undefined,
  });
  emit("BLUEPRINT_LOADED", {
    name: blueprintDefinition.name,
    blocks: targets.size,
    rows: blueprintRows,
    block: spatial ? undefined : blueprintBlock,
    palette: spatial ? blueprintDefinition.palette : undefined,
  });
  if (spatial) emit("STRATEGY_SELECTED", blueprintDefinition.strategy);

  try {
    activePlayer = spawnSimulatedPlayer(
      { dimension, ...start },
      "Archie",
      GameMode.Creative,
    );
    if (spatial) {
      blueprintDefinition.palette.forEach((entry, slot) => {
        activePlayer.setItem(new ItemStack(entry.name, 64), slot, true);
      });
    } else {
      activePlayer.setItem(new ItemStack(blueprintBlock, 64), 0, true);
    }
    startVisionCamera();
    emit("STATE_UPDATED", {
      player: activePlayer.location,
      health: activePlayer.getComponent("minecraft:health")?.currentValue ?? null,
      hunger: activePlayer.getComponent("minecraft:player.hunger")?.currentValue ?? null,
      completion: 0,
      correct: 0,
      missing: targets.size,
      built_actions: [],
    });
  } catch (error) {
    emit("EPISODE_FAILED", { stage: "spawn", error: String(error) });
    return;
  }

  const metrics = {
    total_actions: 0,
    failed_placements: 0,
    repair_attempts: 0,
    repair_successes: 0,
  };

  function inspectLayer(layer, callback, waitedTicks = 0) {
    // Observe diagonally so the requesting player's original position is not
    // between Archie's camera and the completed structure.
    const inspection = add(origin, -2, 0, -(Math.floor(blueprintWidth / 2) + 3));
    const candidates = [...targets.values()].filter((task) => task.relativeY === layer);
    const focus = candidates.reduce((best, task) => {
      if (!best) return task;
      const taskScore = Math.abs(task.relativeX - Math.floor(blueprintWidth / 2)) + task.relativeDepth;
      const bestScore = Math.abs(best.relativeX - Math.floor(blueprintWidth / 2)) + best.relativeDepth;
      return taskScore < bestScore ? task : best;
    }, null);
    if (!focus) {
      callback();
      return;
    }
    if (waitedTicks === 0) {
      emit("VIEWPOINT_SELECTED", { purpose: "layer inspection", layer, destination: inspection, focus: focus.target });
      placementDecision("OBSERVE", `step back to inspect completed layer ${layer + 1}`, focus.target);
      try {
        activePlayer.navigateToLocation(inspection, 1.0);
      } catch (error) {
        emit("VISUAL_CHECK", { layer, visible: false, reason: String(error) });
        callback();
        return;
      }
    }
    if (distance(activePlayer.location, inspection) <= 1.25) {
      try {
        activePlayer.lookAtBlock(focus.target);
        emit("VISUAL_CHECK", {
          layer,
          visible: null,
          reason: "camera-aware inspection sample captured; learned visibility judgment pending",
          focus: focus.target,
        });
      } catch (error) {
        emit("VISUAL_CHECK", { layer, visible: false, reason: String(error), focus: focus.target });
      }
      system.runTimeout(callback, INSPECTION_HOLD_TICKS);
      return;
    }
    if (waitedTicks >= MOVE_TIMEOUT_TICKS) {
      emit("VISUAL_CHECK", { layer, visible: false, reason: "inspection viewpoint was unreachable" });
      callback();
      return;
    }
    system.runTimeout(
      () => inspectLayer(layer, callback, waitedTicks + MOVEMENT_POLL_TICKS),
      MOVEMENT_POLL_TICKS,
    );
  }

  function comparison() {
    let correct = 0;
    const builtActions = [];
    for (const [action, task] of targets.entries()) {
      if (dimension.getBlock(task.target)?.typeId === task.block) {
        correct += 1;
        builtActions.push(action);
      }
    }
    return {
      correct_blocks: correct,
      missing_blocks: targets.size - correct,
      completion: correct / targets.size,
      exact_completion: correct === targets.size,
      built_actions: builtActions,
    };
  }

  function finish() {
    if (pendingPolicy?.episode === episode) {
      system.clearRun(pendingPolicy.timeout);
      pendingPolicy = undefined;
    }
    const result = comparison();
    emit(result.exact_completion ? "EPISODE_COMPLETED" : "EPISODE_FAILED", {
      ...metrics,
      ...result,
      incorrect_blocks: 0,
      extra_blocks: 0,
    });
    system.runTimeout(stopVisionCamera, 1);
  }

  function verifyPlacement(action, attempt, waitedTicks = 0) {
    const task = targets.get(action);
    const observed = dimension.getBlock(task.target)?.typeId ?? null;
    if (observed === task.block) {
      placementDecision("ADVANCE", "intended block was observed", task.target, attempt);
      emit("BLOCK_PLACEMENT_SUCCEEDED", {
        target: task.target,
        intended: task.block,
        observed,
        attempt,
      });
      if (attempt > 1) metrics.repair_successes += 1;
      const state = comparison();
      emit("STATE_UPDATED", {
        player: activePlayer.location,
        health: activePlayer.getComponent("minecraft:health")?.currentValue ?? null,
        hunger: activePlayer.getComponent("minecraft:player.hunger")?.currentValue ?? null,
        completion: state.completion,
        correct: state.correct_blocks,
        missing: state.missing_blocks,
        current_target: task.target,
        built_actions: state.built_actions,
      });
      stateRevision += 1;
      if (spatial) {
        const layerRemaining = [...targets.values()].some(
          (candidate) => candidate.relativeY === task.relativeY
            && dimension.getBlock(candidate.target)?.typeId !== candidate.block,
        );
        if (!layerRemaining && task.relativeY > lastInspectedLayer) {
          lastInspectedLayer = task.relativeY;
          system.runTimeout(() => inspectLayer(task.relativeY, buildNextTarget), 2);
          return;
        }
      }
      system.runTimeout(buildNextTarget, 2);
      return;
    }

    if (waitedTicks < VERIFY_TICKS) {
      system.runTimeout(() => verifyPlacement(action, attempt, waitedTicks + 1), 1);
      return;
    }

    metrics.failed_placements += 1;
    emit("BLOCK_PLACEMENT_FAILED", {
      target: task.target,
      intended: task.block,
      observed,
      attempt,
    });
    if (attempt < MAX_ATTEMPTS) {
      placementDecision("RETRY", "placement was not observed", task.target, attempt);
      metrics.repair_attempts += 1;
      emit("FAULT_DETECTED", { target: task.target, action: "retry", next_attempt: attempt + 1 });
      system.runTimeout(() => placeTarget(action, attempt + 1), 5);
    } else {
      placementDecision("ABORT", "placement retry budget was exhausted", task.target, attempt);
      finish();
    }
  }

  function dispatchPlacement(action, attempt) {
    const task = targets.get(action);
    try {
      emit("BLOCK_PLACEMENT_ATTEMPTED", {
        target: task.target,
        block: task.block,
        attempt,
        policy_action: action,
        total: targets.size,
      });
      const actionAccepted = activePlayer.useItemInSlotOnBlock(
        task.slot,
        task.support,
        Direction.Up,
        { x: 0.5, y: 1.0, z: 0.5 },
      );
      emit("ACTION_DISPATCHED", { actionAccepted, target: task.target, attempt });
      placementDecision("VERIFY", "waiting to observe placement result", task.target, attempt);
    } catch (error) {
      emit("BLOCK_PLACEMENT_FAILED", { target: task.target, attempt, error: String(error) });
    }
    system.runTimeout(() => verifyPlacement(action, attempt, 1), 1);
  }

  function placeTarget(action, attempt) {
    const task = targets.get(action);
    metrics.total_actions += 1;
    try {
      activePlayer.lookAtBlock(task.support);
      placementDecision("PLACE", "aimed from a reachable construction vantage", task.target, attempt);
      system.runTimeout(() => dispatchPlacement(action, attempt), AIM_SETTLE_TICKS);
    } catch (error) {
      emit("BLOCK_PLACEMENT_FAILED", { target: task.target, attempt, error: String(error) });
      system.runTimeout(() => verifyPlacement(action, attempt, AIM_SETTLE_TICKS), 1);
    }
  }

  function waitForTarget(action, waitedTicks = 0) {
    const task = targets.get(action);
    if (distance(activePlayer.location, task.stand) <= arrivalThreshold) {
      placeTarget(action, 1);
      return;
    }
    if (waitedTicks >= MOVE_TIMEOUT_TICKS) {
      prepareTarget(action);
      return;
    }
    system.runTimeout(
      () => waitForTarget(action, waitedTicks + MOVEMENT_POLL_TICKS),
      MOVEMENT_POLL_TICKS,
    );
  }

  function prepareTarget(action, repositionAttempts = 0) {
    const task = targets.get(action);
    const remaining = distance(activePlayer.location, task.stand);
    if (remaining <= arrivalThreshold) {
      placeTarget(action, 1);
      return;
    }
    if (repositionAttempts >= MAX_ATTEMPTS) {
      placementDecision("ABORT", "target remained unreachable after repositioning", task.target);
      finish();
      return;
    }
    placementDecision("REPOSITION", `target is ${remaining.toFixed(2)} blocks from stand point`, task.target);
    try {
      activePlayer.navigateToLocation(task.stand, 1.0);
    } catch (error) {
      emit("EPISODE_FAILED", { stage: "reposition", target: task.target, error: String(error) });
      return;
    }
    system.runTimeout(() => prepareTarget(action, repositionAttempts + 1), 20);
  }

  function buildNextTarget() {
    let fallback = null;
    if (spatial) {
      const valid = [];
      for (const [action, task] of targets.entries()) {
        if (dimension.getBlock(task.target)?.typeId === task.block) continue;
        if (task.relativeY === 0 || dimension.getBlock(task.support)?.typeId !== "minecraft:air") {
          valid.push(action);
        }
      }
      if (valid.length === 0) {
        finish();
        return;
      }
      executeDecision(valid[0], "spatial-blueprint-planner-v0", valid);
      return;
    }
    const blueprint = Array(25).fill(0);
    const built = Array(25).fill(0);
    for (const [action, task] of targets.entries()) {
      blueprint[action] = 1;
      if (dimension.getBlock(task.target)?.typeId === task.block) built[action] = 1;
    }
    fallback = selectNeuralObjective(blueprint, built);

    function executeDecision(action, policy, allowed = fallback.valid) {
      if (!allowed.includes(action)) {
        rejectExternalDecision("invalid action reached execution gate", { episode, revision: stateRevision, action });
        action = fallback?.action ?? allowed[0];
        policy = fallback ? "objective-selector-v0-fallback" : "spatial-blueprint-planner-v0-fallback";
      }
      if (!spatial && action === COMPLETE_ACTION) {
        finish();
        return;
      }
      const task = targets.get(action);
      emit("OBJECTIVE_SELECTED", {
        target: task.target,
        block: task.block,
        policy,
        policy_action: action,
        valid_actions: allowed,
        selected_logit: fallback?.logits?.[action] ?? null,
        episode,
        revision: stateRevision,
        total: targets.size,
      });
      emit("MOVEMENT_STARTED", { destination: task.stand, target: task.target });
      placementDecision("APPROACH", "move to a supported interaction position", task.target);
      try {
        activePlayer.navigateToLocation(task.stand, 1.0);
      } catch (error) {
        emit("EPISODE_FAILED", { stage: "navigation", target: task.target, error: String(error) });
        return;
      }
      system.runTimeout(() => waitForTarget(action), 1);
    }

    if (externalToken) {
      requestExternalDecision(episode, stateRevision, blueprint, built, fallback, executeDecision);
    } else {
      executeDecision(fallback.action, "objective-selector-v0");
    }
  }

  // Let transient command/join chat fade before a labeled vision build.
  system.runTimeout(buildNextTarget, visionPlayer ? VISION_SETTLE_TICKS : 0);
}

system.afterEvents.scriptEventReceive.subscribe((event) => {
  if (event.id === STRUCTURE_COMMAND) {
    if (event.sourceEntity?.typeId !== "minecraft:player") {
      world.sendMessage("§c[Archie] Structure input must be issued by a player.§r");
      return;
    }
    try {
      selectedBlueprint = parseStructure(event.message);
      world.sendMessage(
        `§5[Archie]§r Spatial blueprint loaded: §f${selectedBlueprint.name}§r (${selectedBlueprint.cells.length} blocks).`,
      );
    } catch (error) {
      world.sendMessage(`§c[Archie] Structure rejected: ${String(error.message ?? error)}.§r`);
    }
    return;
  }
  if (event.id === BLUEPRINT_COMMAND) {
    if (event.sourceEntity?.typeId !== "minecraft:player") {
      world.sendMessage("§c[Archie] Blueprint input must be issued by a player.§r");
      return;
    }
    try {
      selectedBlueprint = parseBlueprint(event.message);
      const blocks = selectedBlueprint.rows.reduce(
        (count, row) => count + [...row].filter((cell) => cell === "1").length,
        0,
      );
      world.sendMessage(`§5[Archie]§r Blueprint loaded: §f${selectedBlueprint.name}§r (${blocks} blocks).`);
    } catch (error) {
      world.sendMessage(`§c[Archie] Blueprint rejected: ${String(error.message ?? error)}.§r`);
    }
    return;
  }
  if (event.id === EXTERNAL_ACTION_COMMAND) {
    let value;
    try {
      value = JSON.parse(event.message);
    } catch {
      rejectExternalDecision("invalid JSON");
      return;
    }
    if (!pendingPolicy) {
      rejectExternalDecision("no decision is pending");
      return;
    }
    if (!externalToken || value.token !== externalToken) {
      rejectExternalDecision("authentication failed");
      return;
    }
    if (value.episode !== pendingPolicy.episode || value.revision !== pendingPolicy.revision) {
      rejectExternalDecision("stale or cross-episode decision", {
        episode: value.episode,
        revision: value.revision,
      });
      return;
    }
    if (!Number.isInteger(value.action) || !pendingPolicy.valid.includes(value.action)) {
      rejectExternalDecision("action is not physically valid", { action: value.action });
      return;
    }
    const request = pendingPolicy;
    pendingPolicy = undefined;
    system.clearRun(request.timeout);
    emit("POLICY_DECISION_APPLIED", {
      episode: value.episode,
      revision: value.revision,
      action: value.action,
      source: value.source ?? "vision-fused-policy-v1",
    });
    request.callback(value.action, value.source ?? "vision-fused-policy-v1");
    return;
  }
  if (event.id === EXTERNAL_OFF_COMMAND) {
    externalToken = undefined;
    world.sendMessage("§5[Archie]§r External policy disabled; Objective Selector V0 fallback is active.");
    return;
  }
  if (event.id === EXTERNAL_ON_COMMAND) {
    const token = event.message.trim();
    if (event.sourceEntity?.typeId !== "minecraft:player" || token.length < 16) {
      world.sendMessage("§c[Archie] External policy requires a player-issued token of at least 16 characters.§r");
      return;
    }
    externalToken = token;
    world.sendMessage("§5[Archie]§r External fused-policy gate armed for this world session.");
    return;
  }
  if (event.id === VISION_OFF_COMMAND) {
    if (event.sourceEntity?.typeId === "minecraft:player") {
      stopVisionCamera(event.sourceEntity);
    } else {
      stopVisionCamera();
    }
    return;
  }
  if (event.id === VISION_ON_COMMAND) {
    if (!event.sourceEntity || event.sourceEntity.typeId !== "minecraft:player") return;
    stopVisionCamera();
    visionPlayer = event.sourceEntity;
    visionPlayer.runCommand("hud @s hide all");
    visionPlayer.sendMessage("§5[Archie]§r Vision camera armed for the next build. Run §f/scriptevent archie:vision_off§r to cancel.");
    startVisionCamera();
    return;
  }
  if (event.id !== COMMAND) return;
  if (!event.sourceEntity || event.sourceEntity.typeId !== "minecraft:player") {
    emit("EPISODE_FAILED", { stage: "command", error: "Run the command as a player." });
    return;
  }
  startPhysicalBuild(event.sourceEntity);
});

world.afterEvents.worldLoad.subscribe(() => {
  world.sendMessage("§5[Archie V0.4.7]§r Ready. Run §f/scriptevent archie:start§r as an operator.");
});

