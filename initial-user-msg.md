I've been experimenting the past year with the following, and I'm trying to find the best basis for integration into a single development and cognitive framework. I'm a student in graduate AI/ML program at carnegie mellon. I want you to research this thoroughly and reflectively, and help me find the correct (and practically correct!) backbone and synthesis. 

1. Code Assistants (in no specific order)
 - Claude Code
 - Codex CLI
 - Codex Desktop
 - Claude Desktop
 - Pi Coding Assistant
 - Goose
 - OpenCode
 - Various assistants in vscode

2. Web Orchestration + Development Pipelines + Cognitive Disciplines (~/workspace/noetic-pi and more recent ~/workspace/noetic-pi-docker to disambiguate developed product from development basis)
 - Built over Pi Coding Assistant
 - Has "APM" (agent population manager) state machine
 - APM interacts with "agent mesh" extension in Pi
 - Has cognitive disciplines with agentic pipelines structured on normative cognitive process
 - Has development pipelines with phases: design_intent->abstract_design->implementation_procedure_design->implementation
 - Each development pipeline phase has a cycles=n loop(QA->Remediation) and is multi-agent
 - Agents are given unique ordinals
 - Also has embedding and summarization for sessions

3. "Telos" goalchain project (~/workspace/telos)
 - goalchains, subgoals, principles & immutables, reproductive clause
 - intent to make it multi-agent in some respect
 - MCP/extension integration with OpenCode and Pi, works in both

4. Inference Engines local with 2x 3090 RTX GPUs
 - llama.cpp with Qwen3.6-A3B + vision
 - ollama with snowflake embedding model
 - another ollama instance with Qwen3-ASR-1.7B
 - possibly others, I don't recall

5. Model training project (~/workspace/saeproj)
 - Insight is that there might be benefit to training models to recognize universally-invariant patterns in the processes that generate any instance of intelligent artifact - attentiveness/description, inquiry/insight, critical-reflection/judgment, deliberation/decision
 - Based on gemma model training
 - Has been worked on intermittently
 - Tied to user's notion that current AI/ML engineering is like alchemy without the periodic table, lacking any common standard model of cognition

6. IBM ContextForge Exploration (server listening on 4444)
 - Original idea was single MCP host with flexible distribution patterns with stdio-packet and packet-stdio bridges
 - project cf-controlplane is a messy effort to make it easier but not fruitful thus far

7. (~/workspace/genus-router) project
 - idea here was a MCP server for model selection based on composite/intersection of multiple dimensions of task-to-capability relationships across those dimensions

8. General themes of sound cognitive modeling
 - /home/dgk/workspace/saeproj/docs/[transcendental-method-structured.txt,on_emergent_fidelity.txt,the-notion-of-judgement.txt,theoretical_foundations.md]

