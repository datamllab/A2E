import type { AgentInfo } from "../api/types";

export const MODEL_OPTIONS = ["gpt-5.5", "gpt-4.1", "claude-3.7-sonnet", "qwen-max"] as const;

export const AGENT_FALLBACK: AgentInfo[] = [
  { id: "agno", label: "Agno" },
  { id: "anthropic", label: "Anthropic" },
  { id: "autogen-agentchat", label: "AutoGen", aliases: ["autogen", "autogen_agentchat"] },
  { id: "claude-agent-sdk", label: "Claude SDK", aliases: ["claude-sdk", "claude_sdk", "claudesdk"] },
  { id: "crewai", label: "CrewAI" },
  { id: "google-adk", label: "Google ADK", aliases: ["google_adk"] },
  { id: "langchain", label: "LangChain / LangGraph", aliases: ["langgraph", "lang_chain"] },
  { id: "llama-index", label: "LlamaIndex", aliases: ["llama_index"] },
  { id: "openai", label: "OpenAI" },
  { id: "openai-agents", label: "OpenAI Agents", aliases: ["openai_agents"] },
  { id: "smolagents", label: "Smolagents" },
];
