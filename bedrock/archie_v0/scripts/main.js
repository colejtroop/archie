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
const MOVE_TICKS = 60;
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

function startPhysicalPlacement(source) {
  disconnectActivePlayer();

  const dimension = source.dimension;
  const origin = blockPosition(source.location);
  const start = add(origin, -3, 0, 0);
  const stand = add(origin, 1, 0, 0);
  const support = add(origin, 2, -1, 0);
  const target = add(support, 0, 1, 0);

  // Direct editing is restricted to the repeatable test fixture. The target
  // itself is always placed by the simulated player's selected inventory item.
  dimension.getBlock(support)?.setType("minecraft:bedrock");
  dimension.getBlock(target)?.setType("minecraft:air");
  dimension.getBlock(start)?.setType("minecraft:air");
  dimension.getBlock(stand)?.setType("minecraft:air");

  emit("EPISODE_STARTED", { origin, target, block: BLOCK_TYPE });

  try {
    activePlayer = spawnSimulatedPlayer(
      { dimension, ...start },
      "Archie",
      GameMode.creative,
    );
    activePlayer.setItem(new ItemStack(BLOCK_TYPE, 64), 0, true);
    emit("STATE_UPDATED", {
      player: activePlayer.location,
      health: activePlayer.getComponent("minecraft:health")?.currentValue ?? null,
      hunger: activePlayer.getComponent("minecraft:player.hunger")?.currentValue ?? null,
    });
    emit("MOVEMENT_STARTED", { destination: stand });
    activePlayer.navigateToLocation(stand, 1.0);
  } catch (error) {
    emit("EPISODE_FAILED", { stage: "spawn", error: String(error) });
    return;
  }

  system.runTimeout(() => {
    try {
      activePlayer.lookAtBlock(support);
      emit("BLOCK_PLACEMENT_ATTEMPTED", { target, block: BLOCK_TYPE });
      const actionAccepted = activePlayer.useItemInSlotOnBlock(
        0,
        support,
        Direction.Up,
        { x: 0.5, y: 1.0, z: 0.5 },
      );
      emit("ACTION_DISPATCHED", { actionAccepted });
    } catch (error) {
      emit("BLOCK_PLACEMENT_FAILED", { target, error: String(error) });
    }

    system.runTimeout(() => {
      const observed = dimension.getBlock(target)?.typeId ?? null;
      const success = observed === BLOCK_TYPE;
      emit(
        success ? "BLOCK_PLACEMENT_SUCCEEDED" : "BLOCK_PLACEMENT_FAILED",
        { target, intended: BLOCK_TYPE, observed },
      );
      emit(success ? "EPISODE_COMPLETED" : "EPISODE_FAILED", {
        exact_completion: success,
        correct_blocks: success ? 1 : 0,
        missing_blocks: success ? 0 : 1,
      });
    }, VERIFY_TICKS);
  }, MOVE_TICKS);
}

world.afterEvents.scriptEventReceive.subscribe((event) => {
  if (event.id !== COMMAND) return;
  if (!event.sourceEntity || event.sourceEntity.typeId !== "minecraft:player") {
    emit("EPISODE_FAILED", { stage: "command", error: "Run the command as a player." });
    return;
  }
  startPhysicalPlacement(event.sourceEntity);
});

world.afterEvents.worldLoad.subscribe(() => {
  world.sendMessage("§5[Archie]§r Ready. Run §f/scriptevent archie:start§r as an operator.");
});

