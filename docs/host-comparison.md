# Host Comparison: Claude Desktop vs. Cursor

This document provides a detailed comparative analysis of executing the **Consus Compliance Operations MCP Server** across two different MCP client hosts:
1. **Host 1:** Claude Desktop (Anthropic)
2. **Host 2:** Cursor (AI Code Editor / Agent)

---

## 1. Architectural & Interface Comparison

| Feature / Dimension | Claude Desktop | Cursor (Composer / Agent) |
|---|---|---|
| **Primary Interface** | Conversational Chat UI | Code Editor with Integrated Agent & Composer |
| **Transport Protocol** | `stdio` via local process execution | `stdio` via local process execution |
| **Configuration Path** | `%APPDATA%\Claude\claude_desktop_config.json` | `.cursor/mcp.json` or Settings → Features → MCP |
| **Runtime Target** | `E:\MCP 2\.venv\Scripts\python.exe` | `E:\MCP 2\.venv\Scripts\python.exe` |
| **Working Directory** | Explicitly configured via `"cwd": "E:\\MCP 2"` | Inherits workspace directory or uses `"cwd"` |
| **Default Persona** | Compliance Officer / Governance Advisor | AI Systems Engineer / Infrastructure Operator |
| **Tool Execution Flow** | Multi-turn conversational planning | Timeline-based agent execution with code/file context |

---

## 2. Configuration Specifications

### A. Claude Desktop Configuration
File path: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "consus-compliance": {
      "command": "E:\\MCP 2\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.server"],
      "cwd": "E:\\MCP 2",
      "env": {
        "PYTHONPATH": "E:\\MCP 2",
        "LLM_PROVIDER": "fallback"
      }
    }
  }
}
```

---

### B. Cursor Configuration
File path: `E:\MCP 2\.cursor\mcp.json`

```json
{
  "mcpServers": {
    "consus-compliance": {
      "command": "E:\\MCP 2\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.server"],
      "cwd": "E:\\MCP 2",
      "env": {
        "PYTHONPATH": "E:\\MCP 2",
        "LLM_PROVIDER": "fallback"
      }
    }
  }
}
```

---

## 3. Tool Discovery & Protocol Support

Both hosts discover all **8 MCP tools**, **1 MCP resource**, and **1 MCP prompt** over stdio JSON-RPC:

| MCP Primitive | Claude Desktop Behavior | Cursor Agent Behavior |
|---|---|---|
| `ingest_company_documents` | Ingests multi-format (.pdf, .docx, .txt, .md) policies for any customer ID into isolated index. | Ingests project files directly; displays chunk count and document versions. |
| `analyze_compliance` | Evaluates requirements via RAG; triggers PDF Gap Report generation; outputs concise bullet-point summary. | Runs RAG analysis; returns structured JSON in execution timeline. |
| `get_compliance_suggestions` | Formats actionable policy clauses and remediation steps for human compliance officers. | Suggests policy clauses directly for editing in the code editor workspace. |
| `create_compliance_task` | Enforces strict validation (rejects MATCH findings); creates tracked remediation tasks. | Generates tasks with priority and team assignments in SQLite. |
| `assign_compliance_task` | Routes tasks to eligible teams (Security, Compliance, Infrastructure, IT). | Assigns tasks based on component scope. |
| `update_task_status` | Updates lifecycle state (`OPEN`, `IN_PROGRESS`, `RESOLVED`, etc.). | Updates SQLite task lifecycle state. |
| `recheck_requirement` | Re-evaluates updated v2 policies; auto-resolves tasks on MATCH. | Verifies remediated policies and confirms task resolution. |
| `generate_compliance_report` | Outputs full Markdown readiness report and generates signed PDF readiness report. | Displays report metrics and confirms readiness for human sign-off. |
| **Resource** (`consus://requirements`) | Read-only catalog of representative defense AI compliance requirements. | Supported via programmatic MCP resource read. |
| **Prompt** (`compliance_readiness_assessment`) | Interactive conversation template guiding user through full workflow. | Can be provided as instructions in Composer. |

---

## 4. Key Strengths & Comparative Analysis

### Claude Desktop Strengths:
1. **Executive Tone & Governance Focus:** Claude's conversational interface excels at providing short, point-wise, non-technical summaries that compliance officers and executive stakeholders can immediately understand.
2. **Autonomous Tool Chaining:** When asked to "evaluate Company Y's compliance readiness", Claude automatically sequences ingestion → gap analysis → suggestion review → task creation → re-check → final report.
3. **Artifact Presentation:** Displays the Markdown Compliance Readiness Report directly in the chat window with clear metrics tables.

### Cursor Strengths:
1. **Engineering Remediation Workflow:** Cursor's side-by-side editor allows engineers to receive remediation suggestions from `get_compliance_suggestions` and immediately edit or author the updated policy file (e.g. `access_control_policy_v2.docx` or `data_boundary_policy_v2.md`) right inside the workspace.
2. **Interactive Debugging & Script Execution:** In Agent mode, Cursor can run unit tests (`pytest tests -v`) and verify the MCP handshake live without leaving the editor.
3. **Direct File System Access:** Allows seamless inspection of the generated PDF reports in `data/reports/`.
