# P3 Architecture

This document describes the intended production architecture for the P3 Agent layer, including the Copilot, Supervisor, specialist workers, and runtime behavior.

## 1. Purpose

The role of P3 is to provide the intelligent conversational agent and reasoning capabilities for the Seekr platform. 

- P3 consumes retrieval interfaces exposed by P2.
- P3 never directly accesses Neo4j, PostgreSQL, or Qdrant.
- P3 owns all reasoning and LLM interaction.

## 2. Ownership

**P2 owns:**
- HTTP API definitions
- Basic request validation
- Retrieval
- Hybrid Search
- Graph Retrieval
- Public retrieval interfaces
- RetrievalContext
- GraphContext
- Citations
- `retrieve()`
- `context_graph_query()`

**P3 owns:**
- Copilot
- Supervisor
- Asset Worker
- Diagnose Worker
- Compliance Worker
- LangGraph
- Prompt construction
- LLM invocation
- Reasoning
- Tool orchestration
- Conversation state
- Streaming orchestration
- Audit logging

## 3. LangGraph Architecture

The system uses exactly one graph:

```text
Supervisor
↓
Asset
Diagnose
Compliance
```

There is NOT one graph per worker. The Supervisor acts as the single routing entry point for escalated queries and routes the request to the appropriate specialist worker within the single graph execution.

The LangGraph execution begins only after the Copilot decides that specialized reasoning is required. Normal Copilot responses do not execute the LangGraph.

## 4. Component Responsibilities

### Copilot

- Entry point for all `/query` requests.
- Calls `retrieve()`.
- Produces the initial streamed response.
- Determines whether escalation is required.
- Never performs specialist reasoning.

### Supervisor

- Receives only escalated requests.
- Selects exactly one specialist worker.
- Performs routing only.
- Never performs retrieval, prompt construction, or LLM invocation.

### Specialist Workers

- Perform domain-specific reasoning.
- Use `retrieve()` and `context_graph_query()`.
- Stream reasoning and tool events.
- Never access databases directly.

**Asset**: Handles queries related to specific entities, historical operational data, maintenance history, and telemetry.
**Diagnose**: Investigates root causes, correlates anomalies across the knowledge graph, and provides troubleshooting procedures.
**Compliance**: Verifies adherence to regulations, safety protocols, and operational standards.

## 5. Shared State

- **ConversationContext**: Represents the ongoing conversation history and user session data.
- **EscalationContext**: Passed between the Copilot and the Supervisor when specialized reasoning is needed. It explicitly carries the following between Copilot and Supervisor:
  - `query`
  - `session_id`
  - `thread_id`
  - `focused_tag`
  - `retrieval_context`
  - `citations`
  - `trigger_reason`
  - `trigger_confidence`
  - optional `copilot_answer`
- **AgentState**: The internal state within the LangGraph execution. Explicit endpoints (`POST /asset`, `POST /diagnose`, `POST /comply`) bypass the Copilot and Supervisor, therefore they do NOT create an `EscalationContext`. Instead, they construct the initial `AgentState` directly from the `AgentRequest` before entering the worker workflow.

## 6. Streaming Contract

The system utilizes Server-Sent Events (SSE) for streaming the response back to the client.

**Normal Query Lifecycle:**
`token`* -> `citation`* -> `done`

**Escalated Query Lifecycle:**
`token`* -> `citation`* -> `agent_trigger` -> `reasoning`* -> `tool_call`* -> `tool_result`* -> `token`* -> `citation`* -> `done`

**Contract Rules:**
- one `POST /query` creates one SSE stream
- the stream remains open until the request lifecycle completes
- `done` is emitted exactly once
- `done` is always the final event
- no event follows `done`
- no second SSE connection is required
- worker execution occurs within the same request lifecycle

**Copilot Escalation Behavior:**
The Copilot's initial answer is streamed immediately. If escalation occurs, the worker augments the existing stream. The Copilot answer is never discarded or replaced.

## 7. Folder Structure

The intended directory structure for P3 is:

```text
backend/app/agents/
    copilot/
    supervisor/
    asset/
    diagnose/
    comply/
    shared/
```

## 8. Design Principles

- Copilot is not a worker.
- Supervisor performs routing only.
- Workers never access databases directly.
- Workers interact with P2 exclusively through the public interfaces `retrieve()` and `context_graph_query()`.
- Retrieval belongs entirely to P2.
- All LLM interaction belongs entirely to P3.
- P3 never bypasses `retrieve()` or `context_graph_query()`.
- Internal implementation may evolve while public interfaces remain stable.

## 9. Implementation Roadmap

1. Architecture Freeze
2. P3 Scaffolding
3. Shared Infrastructure
4. Supervisor
5. Copilot
6. Asset Worker
7. Diagnose Worker
8. Compliance Worker
9. LangGraph Integration
10. Testing

## 10. Runtime Execution Flow

### General Query

```text
User
↓
POST /query
↓
HTTP API (P2)
↓
P3 Copilot
↓
retrieve()
↓
LLM Generation
↓
Trigger Evaluation
↓
Need specialized reasoning?
├── No → Continue streaming → done
└── Yes
      ↓
   agent_trigger
      ↓
   Supervisor
      ↓
   Selected Worker
      ↓
retrieve()
↓
context_graph_query()
↓
Worker reasoning
↓
Continue streaming
↓
done
```

### Explicit Agent Invocation

```text
POST /asset
POST /diagnose
POST /comply
↓
Dedicated Agent
↓
retrieve()
context_graph_query()
```

These explicit endpoints bypass the standard routing logic because the target agent is already known.

## 11. Known Documentation Supersession

Some older planning documents in the repository may predate the finalized architecture. In particular, older Stage 1 planning documents may describe query classification as a P2-owned deliverable, omit the Copilot path entirely, or route every request through the Supervisor. These documents should be treated as historical planning artifacts. The architecture defined in this document supersedes those earlier descriptions.

## 12. Supervisor Routing Rules

The Supervisor is only responsible for routing. It must always resolve to exactly one of the specialist workers: Asset Worker, Diagnose Worker, or Compliance Worker. If routing cannot be resolved, the Supervisor must follow a defined logged fallback path. It must never silently terminate or leave the request unresolved.
