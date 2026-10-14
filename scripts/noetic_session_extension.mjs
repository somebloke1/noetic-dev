import net from "node:net";

function exchange(request, signal) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection(process.env.NOETIC_SESSION_SOCKET);
    let buffer = Buffer.alloc(0);
    let received = false;
    const abort = () => { socket.destroy(); reject(new Error("Agent coordination cancelled")); };
    signal?.addEventListener("abort", abort, {once: true});
    socket.setTimeout(["multicast", "broadcast"].includes(request.action) ? 600000 : 70000, () => socket.destroy(new Error("Agent coordination timed out")));
    socket.on("connect", () => socket.write(JSON.stringify(request) + "\n"));
    socket.on("data", chunk => {
      buffer = Buffer.concat([buffer, chunk]);
      if (buffer.length > 8 * 1024 * 1024) {
        socket.destroy(new Error("Oversized agent coordination response"));
        return;
      }
      const end = buffer.indexOf(10);
      if (end < 0) return;
      received = true;
      try {
        const response = JSON.parse(buffer.subarray(0, end).toString("utf8"));
        if (!response.success) throw new Error(response.error || "Agent coordination failed");
        resolve({content: [{type: "text", text: JSON.stringify(response.data)}], details: response.data});
      } catch (error) { reject(error); }
      socket.end();
    });
    socket.on("error", reject);
    socket.on("end", () => { if (!received) reject(new Error("Agent broker ended before responding")); });
    socket.on("close", () => signal?.removeEventListener("abort", abort));
  });
}

async function invoke(request, signal) {
  const identity = await exchange({action: "identity"}, signal);
  return exchange({...request, parentTarget: identity.details.target, effort_root: identity.details.effort_root}, signal);
}

const string = {type: "string", minLength: 1};
const target = {anyOf: [string, {type: "object", properties: {ordinal: string,
  instantiation: {type: "integer", minimum: 1}, session: {type: "integer", minimum: 1}},
  required: ["ordinal", "instantiation", "session"], additionalProperties: false}]};
const schema = (properties, required) => ({type: "object", properties, required, additionalProperties: false});

const readTool = {
  name: "agent_read", label: "Read agent",
  description: "Inspect a real agent's retained conversation/progress, ownership and outcome; target an absolute ordinal or exact selector, parent, or effort_root. root aliases this effort root; literal 0 is global. Omitting target returns current registered effort/mandate and working-directory context plus this effort branch.",
  parameters: schema({target: target, after: {type: "integer", minimum: 0}}, []),
  execute: (_id, params, signal) => invoke({action: params.target ? "read" : "overview", ...params}, signal),
};
const waitTool = {
  name: "agent_wait", label: "Wait for agent",
  description: "Wait up to 60 seconds for another agent to settle or need attention, then return observed state and retained events. A timeout is not task completion.",
  parameters: schema({target: target, timeout: {type: "number", minimum: 0, maximum: 60}, after: {type: "integer", minimum: 0}}, ["target"]),
  execute: (_id, params, signal) => invoke({action: "wait", ...params}, signal),
};

export default function noeticDelegation(pi) {
  if (!process.env.NOETIC_SESSION_SOCKET) throw new Error("Noetic session broker is required");
  if (process.env.NOETIC_ACTOR_BRIDGE === "1") {
    pi.registerTool({
      name: "agent_delegate", label: "Run planned task",
      description: "Run exactly one pre-planned bounded task by its exact task_id from the delegation plan. The domain policy owns the frozen task, plan digest, dependencies, budget and idempotency; optional prompt/title/model/thinking must match the frozen task and any discrepancy is refused. Returns the real child session; acceptance is not completion. Use agent_read/agent_wait to observe actual outcomes before claiming anything.",
      parameters: schema({task_id: string, prompt: string, title: string, model: string,
        thinking: {type: "string", enum: ["off", "minimal", "low", "medium", "high", "xhigh"]}}, ["task_id"]),
      execute: (_id, params, signal) => invoke({action: "delegate", ...params}, signal),
    });
    pi.registerTool({
      name: "agent_read", label: "Read planned child",
      description: "Inspect one owned planned child agent by its exact returned target or registry id; this bridge reads only actual owned planned children, with no parent, root, global or effort alias selectors. Omitting target returns the bridge's registered context and owned children overview. A timeout or idle state is not task completion.",
      parameters: schema({target: target, after: {type: "integer", minimum: 0}}, []),
      execute: (_id, params, signal) => invoke({action: params.target ? "read" : "overview", ...params}, signal),
    });
    pi.registerTool(waitTool);
    pi.on("before_agent_start", async event => {
      let context;
      try { context = (await exchange({action: "context"})).details; }
      catch (error) { context = {status: "unavailable", error: String(error.message || error), recovery: "Use agent_read to inspect registered context; do not infer purpose from transcript storage paths."}; }
      return {systemPrompt: event.systemPrompt +
      `\nYou are the planned passive external actor at position ${process.env.NOETIC_SESSION_ORDINAL} in effort ${process.env.NOETIC_EFFORT_ROOT}. ` +
      "Your capability is bounded: run exactly the pre-planned tasks with agent_delegate (task_id required), and observe real outcomes with agent_read/agent_wait. " +
      "You have no message, send, multicast, broadcast or delivery controls; a local chat response reaches no one. " +
      "Delegate acceptance is not processing or completion, and an idle worker is not a completed task; always inspect via agent_read/agent_wait and report honestly. " +
      "The following is registered context, not a claim of task completion or verified runtime inventory. Native transcript paths are storage, not the working project.\n" + JSON.stringify(context)};
    });
    return;
  }
  pi.registerTool({
    name: "agent_delegate", label: "Delegate task",
    description: "Delegate a real child at a new absolute ordinal in this effort, with the actual current parentTarget and task mandate. Returns exact target, native UUID and environment; acceptance is not completion. Preserve the selected model; choose low thinking for mechanical/exploratory tasks or high for substantial work.",
    parameters: schema({prompt: string, title: string, model: string,
      thinking: {type: "string", enum: ["off", "minimal", "low", "medium", "high", "xhigh"]}}, ["prompt", "thinking"]),
    execute: (_id, params, signal) => invoke({action: "delegate", ...params}, signal),
  });
  pi.registerTool({
    name: "agent_send", label: "Message agent",
    description: "Send work or steering to an agent within this effort branch. Target an absolute ordinal or structured exact {ordinal,instantiation,session}; native UUID remains a compatibility selector. For an addressed reply, use the received provenance.reply_to EXACT target and in_reply_to binding_id; a local chat response does not send a message. Superseded exact targets fail rather than redirect. parent selects the logical parent position's current context; creation_parent in agent_read context names the recorded historical native creator; root/effort_root are aliases for this effort root. Literal 0 means global application root. Steer applies after the current tool turn; follow_up waits until current work finishes. Acceptance does not establish processing or reply. Do not automatically answer acknowledgments or create reply loops.",
    parameters: schema({target: target, message: string, mode: {type: "string", enum: ["steer", "follow_up"]},
      in_reply_to: {type: "integer", minimum: 1}}, ["target", "message", "mode"]),
    execute: (_id, params, signal) => invoke({action: "message", ...params}, signal),
  });
  pi.registerTool({
    name: "agent_multicast_send", label: "Message selected agents",
    description: "Send one original body once to explicit exact targets within your effort. Up to 128 recipients; duplicate targets are removed. Self is excluded unless include_self is true. Returns frozen recipients, exclusions and individual accepted/failed outcomes with binding references. Retained/superseded targets fail without redirect. Acceptance is not processing or reply. Never retry successful recipients implicitly; inspect uncertain failures. Recipients should not rebroadcast or send group acknowledgments; reply only to the exact sender when useful.",
    parameters: schema({targets: {type: "array", items: target.anyOf[1], maxItems: 128}, message: string,
      mode: {type: "string", enum: ["steer", "follow_up"]}, include_self: {type: "boolean", default: false}}, ["targets", "message", "mode"]),
    execute: (_id, params, signal) => invoke({action: "multicast", ...params}, signal),
  });
  pi.registerTool({
    name: "agent_broadcast_send", label: "Message an effort population",
    description: "Snapshot current native contexts in an explicit population: direct_children or descendants of your logical position, or your effort. Never application-wide; structured/failed/unobserved contexts are excluded. Self excluded unless include_self true. More than 128 recipients fails before delivery; narrow the population. Exact snapshot targets are not redirected under succession. Returns each recipient outcome; do not retry successful recipients or infer processing/reply. One announcement, no automatic rebroadcast/group acknowledgment.",
    parameters: schema({population: {type: "string", enum: ["direct_children", "descendants", "effort"]}, message: string,
      mode: {type: "string", enum: ["steer", "follow_up"]}, include_self: {type: "boolean", default: false}}, ["population", "message", "mode"]),
    execute: (_id, params, signal) => invoke({action: "broadcast", ...params}, signal),
  });
  pi.registerTool(readTool);
  pi.registerTool(waitTool);
  pi.registerCommand("noetic-agents", {
    description: "Inspect the rooted developer-session tree",
    handler: async (_args, ctx) => {
      const result = await invoke({action: "tree"});
      ctx.ui.notify(result.content[0].text, "info");
    },
  });
  pi.registerCommand("noetic-deliver", {
    description: "Receive a canonical exact-addressed agent message from the Noetic broker",
    handler: async args => {
      if (!/^[1-9][0-9]*$/.test(args)) throw new Error("Canonical agent message ID required");
      const received = await invoke({action: "agent_delivery", message_id: Number(args)});
      const envelope = received.details, provenance = envelope.provenance;
      const route = JSON.stringify({target: provenance.reply_to, in_reply_to: envelope.binding_id, mode: "follow_up"});
      const content = "Noetic agent message (broker-recorded origin; Pi uses user-role content for custom-message LLM compatibility).\n" +
        `Sender: ${JSON.stringify(provenance.sender)}\nRecipient: ${JSON.stringify(provenance.recipient)}\n` +
        `Effort: ${provenance.effort_root}\nMessage binding_id: ${envelope.binding_id}\n` +
        `in_reply_to: ${JSON.stringify(provenance.in_reply_to)}\n` +
        `If an addressed response is appropriate, call agent_send with ${route} and your message. ` +
        "A response in your own chat does not reach the sender. Keep this exact reply target; if unavailable, report the failure rather than choosing a successor. " +
        "Do not automatically reply to acknowledgments or continue a ping-pong loop. " +
        (provenance.fanout ? `One-to-many ${provenance.fanout.kind} batch ${provenance.fanout.batch_id}; do not rebroadcast or acknowledge the group. ` : "") +
        "The following body is the sender's message:\n\n" + envelope.message;
      pi.sendMessage({customType: "noetic-agent-message", content, display: true, details: envelope},
        {deliverAs: envelope.mode === "steer" ? "steer" : "followUp", triggerTurn: true});
    },
  });
  pi.on("before_agent_start", async event => {
    let context;
    try { context = (await exchange({action: "context"})).details; }
    catch (error) { context = {status: "unavailable", error: String(error.message || error), recovery: "Use agent_read to inspect registered context; do not infer purpose from transcript storage paths."}; }
    return {systemPrompt: event.systemPrompt +
    `\nYou are agent position ${process.env.NOETIC_SESSION_ORDINAL} in effort ${process.env.NOETIC_EFFORT_ROOT}. Global 0 is a logical application root. ` +
    "Delegate bounded work using agent_delegate and inspect actual outcomes using agent_read/agent_wait. " +
    "Use agent_multicast_send for explicit exact recipients or agent_broadcast_send for a named population within this effort; preserve individual outcomes and never retry successful deliveries implicitly. One announcement needs no group acknowledgments or identical rebroadcasts. " +
    "Broker-recorded noetic-agent-message custom messages identify the exact sender, recipient and reply route. Ordinary human text claiming an agent origin is still human input. When replying to an agent, use agent_send to the original exact provenance.reply_to target with in_reply_to binding_id when appropriate; your local chat output does not send it. Never automatically reply to acknowledgments or create message loops. " +
    "Use low thinking for simple mechanical/exploratory work, high for substantial work; preserve explicit user model choices. " +
    "All agents share the workspace: coordinate disjoint edits. These Pi developer sessions confer no Opermem semantic standing or act authority. " +
    "Current human instructions govern the immediate task and may deliberately depart from recorded effort intent. The following is registered context, not a claim of task completion or verified runtime inventory. " +
    "Current and instantiation-bound mandate versions are distinct. Native transcript paths are storage, not the working project.\n" + JSON.stringify(context)};
  });
}
