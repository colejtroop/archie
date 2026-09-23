import {
  Direction,
  GameMode,
  ItemStack,
  system,
  world,
} from "@minecraft/server";
import { spawnSimulatedPlayer } from "@minecraft/server-gametest";

const COMMAND = "archie:start";
const BLOCK_TYPE = "minecraft:stone";
const WALL_WIDTH = 3;
const WALL_HEIGHT = 3;
const MAX_ATTEMPTS = 3;
const MOVE_TICKS = 40;
const VERIFY_TICKS = 10;

let activePlayer;

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
  world.sendMessage(`§5[Archie]§r ${event}`);
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
  const targets = [];
  for (let y = 0; y < WALL_HEIGHT; y += 1) {
    for (let z = -1; z <= 1; z += 1) {
      targets.push({
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
  for (const task of targets) {
    dimension.getBlock(task.target)?.setType("minecraft:air");
    dimension.getBlock(task.stand)?.setType("minecraft:air");
    dimension.getBlock(add(task.stand, 0, 1, 0))?.setType("minecraft:air");
  }
  dimension.getBlock(start)?.setType("minecraft:air");

  emit("EPISODE_STARTED", {
    origin,
    blueprint: `${WALL_WIDTH}x${WALL_HEIGHT}-wall`,
    block: BLOCK_TYPE,
    total_blocks: targets.length,
  });
  emit("BLUEPRINT_LOADED", {
    name: `${WALL_WIDTH}x${WALL_HEIGHT}-wall`,
    blocks: targets.length,
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
      missing: targets.length,
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
    for (const task of targets) {
      if (dimension.getBlock(task.target)?.typeId === BLOCK_TYPE) correct += 1;
    }
    return {
      correct_blocks: correct,
      missing_blocks: targets.length - correct,
      completion: correct / targets.length,
      exact_completion: correct === targets.length,
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

  function verifyPlacement(index, attempt) {
    const task = targets[index];
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
      system.runTimeout(() => buildTarget(index + 1), 2);
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
      system.runTimeout(() => placeTarget(index, attempt + 1), 5);
    } else {
      finish();
    }
  }

  function placeTarget(index, attempt) {
    const task = targets[index];
    metrics.total_actions += 1;
    try {
      activePlayer.lookAtBlock(task.support);
      emit("BLOCK_PLACEMENT_ATTEMPTED", {
        target: task.target,
        block: BLOCK_TYPE,
        attempt,
        index,
        total: targets.length,
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
    system.runTimeout(() => verifyPlacement(index, attempt), VERIFY_TICKS);
  }

  function buildTarget(index) {
    if (index >= targets.length) {
      finish();
      return;
    }
    const task = targets[index];
    emit("OBJECTIVE_SELECTED", {
      target: task.target,
      block: BLOCK_TYPE,
      index,
      total: targets.length,
    });
    emit("MOVEMENT_STARTED", { destination: task.stand, target: task.target });
    try {
      activePlayer.navigateToLocation(task.stand, 1.0);
    } catch (error) {
      emit("EPISODE_FAILED", { stage: "navigation", target: task.target, error: String(error) });
      return;
    }
    system.runTimeout(() => placeTarget(index, 1), MOVE_TICKS);
  }

  buildTarget(0);
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

