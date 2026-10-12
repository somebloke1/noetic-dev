"""Deterministic RPC fixture: no provider, real stdin/stdout and persisted messages."""
import json
import os
from pathlib import Path
import sys
import subprocess
import threading
import time

args = sys.argv[1:]
def option(name):
    return args[args.index(name) + 1]

sid = option("--session-id")
path = Path(option("--session-dir")) / (sid + ".jsonl")
messages = json.loads(path.read_text()) if path.exists() else []
assert "USER_PROVIDED_PASSWORD" not in os.environ
write_lock = threading.Lock()
streaming, queued, abort = False, [], threading.Event()


def emit(record):
    with write_lock:
        sys.stdout.buffer.write(json.dumps(record, ensure_ascii=False).encode() + b"\n")
        sys.stdout.buffer.flush()


def state():
    return {"sessionId": sid, "sessionFile": str(path), "isStreaming": streaming,
            "pendingMessageCount": len(queued), "model": {"provider": option("--model").split("/")[0], "id": option("--model").split("/")[-1]},
            "thinkingLevel": option("--thinking")}


def run(message):
    global streaming
    streaming = True
    abort.clear()
    emit({"type": "agent_start"})
    native_message = message if isinstance(message, dict) else {"role": "user", "content": message}
    emit({"type": "message_end", "message": native_message})
    messages.append(native_message)
    message = native_message["content"]
    emit({"type": "tool_execution_start", "toolCallId": "fixture-tool", "toolName": "bash", "args": {"command": "fixture"}})
    if message == "dialog":
        emit({"type": "extension_ui_request", "id": "dialog-1", "method": "confirm", "title": "Continue?"})
        while not abort.wait(.01) and not any(m.get("role") == "dialog" for m in messages):
            pass
    for _ in range(1000 if message.startswith("slow browser") else 40 if message.startswith("slow") else 3):
        if abort.wait(.01):
            break
    emit({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "real\u2028fixture\u2029delta"}})
    output = {"role": "assistant", "content": [{"type": "text", "text": "result: " + message}], "stopReason": "aborted" if abort.is_set() else "stop"}
    messages.append(output)
    path.write_text(json.dumps(messages))
    emit({"type": "message_end", "message": output})
    emit({"type": "tool_execution_end", "toolCallId": "fixture-tool", "toolName": "bash", "isError": False, "result": {"content": []}})
    emit({"type": "agent_end", "willRetry": False})
    time.sleep(.02)
    if queued:
        following = queued.pop(0)
        run(following)
    else:
        streaming = False
        emit({"type": "agent_settled"})


for raw in sys.stdin.buffer:
    record = json.loads(raw)
    kind = record["type"]
    response = {"type": "response", "id": record.get("id"), "command": kind, "success": True}
    if kind == "get_state":
        response["data"] = state()
    elif kind == "get_messages":
        response["data"] = {"messages": messages}
    elif kind == "get_commands":
        response["data"] = {"commands": [{"name": "noetic-agents"}]}
    elif kind == "prompt":
        if record["message"].startswith("/noetic-deliver "):
            source = """
                const {default:extension} = await import(process.argv[1]);
                const commands = new Map();
                let captured;
                extension({registerTool(){},on(){},registerCommand:(name,command)=>commands.set(name,command),
                    sendMessage:(message,options)=>{captured={role:'custom',...message};}});
                await commands.get('noetic-deliver').handler(process.argv[2]);
                console.log(JSON.stringify(captured));
            """
            delivered = subprocess.run(["node", "--input-type=module", "-e", source,
                Path(option("-e")).as_uri(), record["message"].split(" ",1)[1]], capture_output=True, timeout=15)
            if delivered.returncode:
                response.update(success=False, error=delivered.stderr.decode())
                emit(response)
                continue
            record["message"] = json.loads(delivered.stdout)
        if record["message"] == "reject":
            response.update(success=False, error="fixture rejected prompt")
        elif streaming:
            if "streamingBehavior" not in record:
                response.update(success=False, error="streamingBehavior required")
            else:
                queued.append(record["message"])
                emit({"type": "queue_update", "steering": queued if record["streamingBehavior"] == "steer" else [], "followUp": queued if record["streamingBehavior"] == "followUp" else []})
        else:
            streaming = True
            threading.Thread(target=run, args=(record["message"],), daemon=True).start()
    elif kind == "clear_queue":
        response["data"] = {"steering": [], "followUp": queued.copy()}
        queued.clear()
        emit({"type": "queue_update", "steering": [], "followUp": []})
    elif kind == "abort":
        abort.set()
        while streaming:
            time.sleep(.01)
    elif kind == "extension_ui_response":
        messages.append({"role": "dialog", "content": record})
        continue
    emit(response)
abort.set()
