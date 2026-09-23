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
const BLOCK_TYPE = "minecraft:stone";
const WALL_WIDTH = 3;
const WALL_HEIGHT = 3;
const MAX_ATTEMPTS = 3;
const MOVE_TICKS = 40;
const VERIFY_TICKS = 10;
const POLICY_WIDTH = 5;
const COMPLETE_ACTION = 25;

let activePlayer;

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

function emit(eventType, payload = {}) {
  const event = JSON.stringify({
    event_type: eventType,
    timestamp_ticks: system.currentTick,
    payload,
  });
  console.info(`[ArchieTelemetry] ${event}`);

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

  const dimension = source.dimension;
  const origin = blockPosition(source.location);
  const start = add(origin, -3, 0, 0);
  const targets = new Map();
  for (let y = 0; y < WALL_HEIGHT; y += 1) {
    for (let x = 0; x < WALL_WIDTH; x += 1) {
      const z = x - 1;
      targets.set(y * POLICY_WIDTH + x, {
        target: add(origin, 2, y, z),
        support: add(origin, 2, y - 1, z),
        stand: add(origin, 1, 0, z),
      });
    }
  }

  // Direct editing is restricted to the repeatable test fixture. The target
  // structure itself is always placed by the simulated player's inventory use.
  for (let z = -1; z <= 1; z += 1) {
    dimension.getBlock(add(origin, 2, -1, z))?.setType("minecraft:bedrock");
  }
  for (const task of targets.values()) {
    dimension.getBlock(task.target)?.setType("minecraft:air");
    dimension.getBlock(task.stand)?.setType("minecraft:air");
    dimension.getBlock(add(task.stand, 0, 1, 0))?.setType("minecraft:air");
  }
  dimension.getBlock(start)?.setType("minecraft:air");

  emit("EPISODE_STARTED", {
    origin,
    blueprint: `${WALL_WIDTH}x${WALL_HEIGHT}-wall`,
    block: BLOCK_TYPE,
    total_blocks: targets.size,
    policy: "objective-selector-v0",
  });
  emit("BLUEPRINT_LOADED", {
    name: `${WALL_WIDTH}x${WALL_HEIGHT}-wall`,
    blocks: targets.size,
  });

  try {
    activePlayer = spawnSimulatedPlayer(
      { dimension, ...start },
      "Archie",
      GameMode.Creative,
    );
    activePlayer.setItem(new ItemStack(BLOCK_TYPE, 64), 0, true);
    emit("STATE_UPDATED", {
      player: activePlayer.location,
      health: activePlayer.getComponent("minecraft:health")?.currentValue ?? null,
      hunger: activePlayer.getComponent("minecraft:player.hunger")?.currentValue ?? null,
      completion: 0,
      correct: 0,
      missing: targets.size,
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

  function comparison() {
    let correct = 0;
    for (const task of targets.values()) {
      if (dimension.getBlock(task.target)?.typeId === BLOCK_TYPE) correct += 1;
    }
    return {
      correct_blocks: correct,
      missing_blocks: targets.size - correct,
      completion: correct / targets.size,
      exact_completion: correct === targets.size,
    };
  }

  function finish() {
    const result = comparison();
    emit(result.exact_completion ? "EPISODE_COMPLETED" : "EPISODE_FAILED", {
      ...metrics,
      ...result,
      incorrect_blocks: 0,
      extra_blocks: 0,
    });
  }

  function verifyPlacement(action, attempt) {
    const task = targets.get(action);
    const observed = dimension.getBlock(task.target)?.typeId ?? null;
    if (observed === BLOCK_TYPE) {
      emit("BLOCK_PLACEMENT_SUCCEEDED", {
        target: task.target,
        intended: BLOCK_TYPE,
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
      });
      system.runTimeout(buildNextTarget, 2);
      return;
    }

    metrics.failed_placements += 1;
    emit("BLOCK_PLACEMENT_FAILED", {
      target: task.target,
      intended: BLOCK_TYPE,
      observed,
      attempt,
    });
    if (attempt < MAX_ATTEMPTS) {
      metrics.repair_attempts += 1;
      emit("FAULT_DETECTED", { target: task.target, action: "retry", next_attempt: attempt + 1 });
      system.runTimeout(() => placeTarget(action, attempt + 1), 5);
    } else {
      finish();
    }
  }

  function placeTarget(action, attempt) {
    const task = targets.get(action);
    metrics.total_actions += 1;
    try {
      activePlayer.lookAtBlock(task.support);
      emit("BLOCK_PLACEMENT_ATTEMPTED", {
        target: task.target,
        block: BLOCK_TYPE,
        attempt,
        policy_action: action,
        total: targets.size,
      });
      const actionAccepted = activePlayer.useItemInSlotOnBlock(
        0,
        task.support,
        Direction.Up,
        { x: 0.5, y: 1.0, z: 0.5 },
      );
      emit("ACTION_DISPATCHED", { actionAccepted, target: task.target, attempt });
    } catch (error) {
      emit("BLOCK_PLACEMENT_FAILED", { target: task.target, attempt, error: String(error) });
    }
    system.runTimeout(() => verifyPlacement(action, attempt), VERIFY_TICKS);
  }

  function buildNextTarget() {
    const blueprint = Array(25).fill(0);
    const built = Array(25).fill(0);
    for (const [action, task] of targets.entries()) {
      blueprint[action] = 1;
      if (dimension.getBlock(task.target)?.typeId === BLOCK_TYPE) built[action] = 1;
    }
    const decision = selectNeuralObjective(blueprint, built);
    if (decision.action === COMPLETE_ACTION) {
      finish();
      return;
    }
    const task = targets.get(decision.action);
    emit("OBJECTIVE_SELECTED", {
      target: task.target,
      block: BLOCK_TYPE,
      policy: "objective-selector-v0",
      policy_action: decision.action,
      valid_actions: decision.valid,
      selected_logit: decision.logits[decision.action],
      total: targets.size,
    });
    emit("MOVEMENT_STARTED", { destination: task.stand, target: task.target });
    try {
      activePlayer.navigateToLocation(task.stand, 1.0);
    } catch (error) {
      emit("EPISODE_FAILED", { stage: "navigation", target: task.target, error: String(error) });
      return;
    }
    system.runTimeout(() => placeTarget(decision.action, 1), MOVE_TICKS);
  }

  buildNextTarget();
}

system.afterEvents.scriptEventReceive.subscribe((event) => {
  if (event.id !== COMMAND) return;
  if (!event.sourceEntity || event.sourceEntity.typeId !== "minecraft:player") {
    emit("EPISODE_FAILED", { stage: "command", error: "Run the command as a player." });
    return;
  }
  startPhysicalBuild(event.sourceEntity);
});

world.afterEvents.worldLoad.subscribe(() => {
  world.sendMessage("§5[Archie]§r Ready. Run §f/scriptevent archie:start§r as an operator.");
});

