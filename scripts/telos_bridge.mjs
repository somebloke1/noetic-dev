// JSON stdin/stdout adapter to the real Telos manager, never a native global store.
import { readFileSync, statSync } from "node:fs";
import { isAbsolute, join } from "node:path";
import { pathToFileURL } from "node:url";

function findRunSubgoal(subGoals, objective) {
  const separator = objective.indexOf("\n");
  const header = objective.slice(0, separator);
  const goal = objective.slice(separator + 1);
  const matches = subGoals.filter((subgoal) => {
    const end = subgoal.objective.indexOf("\n");
    if (end < 0) return false;
    const storedHeader = subgoal.objective.slice(0, end);
    // Legacy objectives retain their absolute location, but it is not run identity.
    return storedHeader === header || (
      storedHeader.startsWith(`${header} at `) && isAbsolute(storedHeader.slice(header.length + 4))
    );
  });
  if (matches.length > 1) throw new Error("Ambiguous subgoal association for this run; existing subgoals were left unchanged");
  const [subgoal] = matches;
  if (subgoal && subgoal.objective.slice(subgoal.objective.indexOf("\n") + 1) !== goal) {
    throw new Error("Run goal does not match its associated subgoal; existing subgoal was left unchanged");
  }
  return subgoal;
}

let handle;
try {
  const input = JSON.parse(readFileSync(0, "utf8"));
  if (!input.dbPath || !isAbsolute(input.dbPath) || !input.source || !isAbsolute(input.source)) {
    throw new Error("An explicit absolute dbPath and component source are required");
  }
  const factory = statSync(input.source).isDirectory()
    ? join(input.source, "packages/pi-runtime/src/core-goal-chain-store.ts")
    : input.source;
  const { createPiCoreGoalChainStore } = await import(pathToFileURL(factory).href);
  handle = createPiCoreGoalChainStore({ dbPath: input.dbPath });
  const manager = handle.manager;
  let result;
  if (input.operation === "create") {
    result = manager.createGoalChain({
      primaryGoal: input.goal,
      scope: "global",
      initialSubGoals: [],
      runtimeProvenance: { component: "noetic-dev", source: input.source, dbPath: input.dbPath },
    });
  } else if (input.operation === "list") {
    result = manager.listGoalChains();
  } else {
    const aggregate = manager.getGoalChain(input.chainId);
    if (!aggregate) throw new Error(`Goal chain ${input.chainId} not found`);
    if (input.operation === "get") {
      result = aggregate;
    } else if (input.operation === "begin") {
      let subgoal = findRunSubgoal(aggregate.subGoals, input.objective);
      if (!subgoal) [subgoal] = manager.addSubGoals(input.chainId, [input.objective]);
      if (subgoal.status === "pending" || subgoal.status === "blocked") {
        manager.updateSubGoalStatus({ chainId: input.chainId, subGoalId: subgoal.subGoalId, status: "active" });
      }
      result = { chain_id: input.chainId, subgoal_id: subgoal.subGoalId };
    } else if (input.operation === "record") {
      const subgoal = findRunSubgoal(aggregate.subGoals, input.objective);
      if (!subgoal || subgoal.subGoalId !== input.subGoalId) {
        throw new Error("Subgoal is not associated with this run; use attach first");
      }
      if (input.status !== "active" && input.status !== "complete") throw new Error("Invalid run subgoal status");
      if (subgoal.status !== input.status) {
        manager.updateSubGoalStatus({
          chainId: input.chainId, subGoalId: input.subGoalId, status: input.status,
          learnings: input.status === "complete" ? [input.note] : [],
        });
      }
      if (!aggregate.records.some((record) => record.details === input.note)) {
        manager.updateGoalChain({ chainId: input.chainId, note: input.note });
      }
      result = { chain_id: input.chainId, subgoal_id: input.subGoalId };
    } else {
      throw new Error(`Unknown bridge operation: ${input.operation}`);
    }
  }
  process.stdout.write(JSON.stringify(result) + "\n");
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
} finally {
  handle?.close();
}
