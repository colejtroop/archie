import { system, world } from "@minecraft/server";

system.afterEvents.scriptEventReceive.subscribe((event) => {
  if (event.id !== "archie:ping") return;
  world.sendMessage("§5[Archie]§r DIAGNOSTIC_OK");
});

world.afterEvents.worldLoad.subscribe(() => {
  world.sendMessage("§5[Archie]§r Diagnostic script loaded. Run /scriptevent archie:ping");
});
