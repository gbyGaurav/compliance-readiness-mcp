# Consus Compliance Readiness MCP

An MCP server that helps organizations identify security and compliance gaps in internal policies before deploying sensitive AI workloads.

## 1. Security Gaps

Before deploying sensitive AI workloads, companies need to check whether their security policies meet the required standards.

**Gap Filled by My MCP:** It helps companies find missing security policies, identify compliance gaps, and understand what needs to be fixed before deployment.

## 2. MCP & Its Benefits

Built using **Model Context Protocol (MCP)**, the server allows compatible AI clients to interact with compliance tools.

### Key Features

- Policy analysis using RAG
- Compliance classification: `MATCH`, `PARTIAL`, `MISMATCH`
- Remediation recommendations
- Compliance task management
- Requirement reassessment
- Automated report generation

### MCP Tools

| Tool | Purpose |
|---|---|
| `register_company` | Register a company |
| `scan_company_documents` | Discover policy documents |
| `store_company_documents` | Process and index policies |
| `analyze_compliance` | Identify compliance gaps |
| `get_compliance_suggestions` | Recommend corrective actions |
| `create_compliance_tasks` | Create remediation tasks |
| `assign_compliance_task` | Assign tasks |
| `update_task_status` | Track task progress |
| `recheck_requirement` | Reassess requirements |
| `generate_final_readiness_report` | Generate final report |

## 3. Tech Stack & Environment

| Technology | Purpose |
|---|---|
| Python | Backend development |
| FastMCP | MCP server |
| SQLite | Lightweight database for storing company information, compliance results, tasks, and policy-related metadata |
| RAG + TF-IDF | Relevant policy evidence retrieval |
| pypdf | PDF text extraction |
| python-docx | DOCX text extraction |
| ReportLab | PDF report generation |

### Run the Project

Clone the repository:

```bash
git clone https://github.com/gbyGaurav/compliance-readiness-mcp.git
cd compliance-readiness-mcp
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the demo:

```bash
python scripts/run_demo.py
```

## 4. Project Structure

### System Design

```text
Company Policies
       |
       v
Document Extraction
       |
       v
Text Chunking
       |
       v
SQLite Database Storage
       |
       v
RAG-Based Retrieval
       |
       v
Compliance Analysis
       |
       v
Gap Detection
       |
       v
Remediation Tasks
       |
       v
Requirement Reassessment
       |
       v
Final Readiness Report
```

### Folder Structure

```text
compliance-readiness-mcp/
|
|-- data/
|   |-- policies/
|   |-- reports/
|
|-- docs/
|
|-- scripts/
|
|-- src/
|   |-- database/
|   |-- llm/
|   |-- rag/
|   |   |-- extractor.py
|   |   |-- chunker.py
|   |   |-- vector_store.py
|   |
|   |-- tools/
|
|-- server.py
|-- requirements.txt
|-- README.md
```

## 5. Outputs

- **Compliance Gap Report:** Identifies missing controls, findings, and recommended actions.
- **Final Readiness Report:** Summarizes compliance results, remediation progress, and outstanding gaps.

### Project Demo

[Watch the Project Demo](https://drive.google.com/file/d/1hUFT4YFjgC1Kdc2DcukspOT6A_ypN3NA/view?usp=sharing)

## Author

**Gaurav Deore**

AI/ML & Data Science Engineer

- [GitHub Profile](https://github.com/gbyGaurav)
- [Project Repository](https://github.com/gbyGaurav/compliance-readiness-mcp)
