import type { Level, Tier } from "@/api/types";

export type GraphFilter = { tiers: Tier[]; levels: Level[] };
export const ALL_TIERS: Tier[] = ["A", "B", "C"];
export const ALL_LEVELS: Level[] = ["campaign", "network"];
