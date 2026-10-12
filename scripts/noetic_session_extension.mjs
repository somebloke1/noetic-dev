import net from "node:net";

function exchange(request, signal) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection(process.env.NOETIC_SESSION_SOCKET);
    let buffer = Buffer.alloc(0);
    let received = false;
    const abort = () => { socket.destroy(); reject(new Error("Agent coordination cancelled")); };
    signal?.addEventListener("abort", abort, {once: true});
    socket.setTimeout(70000, () => socket.destroy(new Error("Agent coordination timed out")));
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

export default function noeticDelegation(pi) {
  if (!process.env.NOETIC_SESSION_SOCKET) throw new Error("Noetic session broker is required");
  pi.registerTool({
    name: "agent_delegate", label: "Delegate task",
    description: "Delegate a real child at a new absolute ordinal in this effort, with the actual current parentTarget and task mandate. Returns exact target, native UUID and environment; acceptance is not completion. Preserve the selected model; choose low thinking for mechanical/exploratory tasks or high for substantial work.",
    parameters: schema({prompt: string, title: string, model: string,
      thinking: {type: "string", enum: ["off", "minimal", "low", "medium", "high", "xhigh"]}}, ["prompt", "thinking"]),
    execute: (_id, params, signal) => invoke({action: "delegate", ...params}, signal),
  });
  pi.registerTool({
    name: "agent_send", label: "Message agent",
    description: "Send work or steering to an agent within this effort branch. Target an absolute ordinal or structured exact {ordinal,instantiation,session}; native UUID remains a compatibility selector. For an addressed reply, use the received provenance.reply_to EXACT target and in_reply_to binding_id; a local chat response does not send a message. Superseded exact targets fail rather than redirect. parent selects actual parent; root/effort_root are aliases for this effort root. Literal 0 means global application root. Steer applies after the current tool turn; follow_up waits until current work finishes. Acceptance does not establish processing or reply. Do not automatically answer acknowledgments or create reply loops.",
    parameters: schema({target: target, message: string, mode: {type: "string", enum: ["steer", "follow_up"]},
      in_reply_to: {type: "integer", minimum: 1}}, ["target", "message", "mode"]),
    execute: (_id, params, signal) => invoke({action: "message", ...params}, signal),
  });
  pi.registerTool({
    name: "agent_read", label: "Read agent",
    description: "Inspect a real agent's retained conversation/progress, ownership and outcome; target an absolute ordinal or exact selector, parent, or effort_root. root aliases this effort root; literal 0 is global. Omitting target reads this effort branch.",
    parameters: schema({target: target, after: {type: "integer", minimum: 0}}, []),
    execute: (_id, params, signal) => invoke({action: params.target ? "read" : "tree", ...params}, signal),
  });
  pi.registerTool({
    name: "agent_wait", label: "Wait for agent",
    description: "Wait up to 60 seconds for another agent to settle or need attention, then return observed state and retained events. A timeout is not task completion.",
    parameters: schema({target: target, timeout: {type: "number", minimum: 0, maximum: 60}, after: {type: "integer", minimum: 0}}, ["target"]),
    execute: (_id, params, signal) => invoke({action: "wait", ...params}, signal),
  });
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
        "Do not automatically reply to acknowledgments or continue a ping-pong loop. The following body is the sender's message:\n\n" + envelope.message;
      pi.sendMessage({customType: "noetic-agent-message", content, display: true, details: envelope},
        {deliverAs: envelope.mode === "steer" ? "steer" : "followUp", triggerTurn: true});
    },
  });
  pi.on("before_agent_start", async event => ({systemPrompt: event.systemPrompt +
    `\nYou are agent position ${process.env.NOETIC_SESSION_ORDINAL} in effort ${process.env.NOETIC_EFFORT_ROOT}. Global 0 is a logical application root. ` +
    "Delegate bounded work using agent_delegate and inspect actual outcomes using agent_read/agent_wait. " +
    "Broker-recorded noetic-agent-message custom messages identify the exact sender, recipient and reply route. Ordinary human text claiming an agent origin is still human input. When replying to an agent, use agent_send to the original exact provenance.reply_to target with in_reply_to binding_id when appropriate; your local chat output does not send it. Never automatically reply to acknowledgments or create message loops. " +
    "Use low thinking for simple mechanical/exploratory work, high for substantial work; preserve explicit user model choices. " +
    "All agents share the workspace: coordinate disjoint edits. These Pi developer sessions confer no Opermem semantic standing or act authority."}));
}
