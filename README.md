# Consus Compliance Readiness MCP

An MCP server that helps companies check whether their internal policies are ready before deploying sensitive AI workloads on secure and compliant infrastructure.

## 🎥 Demo

[Watch the Project Demo](https://drive.google.com/file/d/1hUFT4YFjgC1Kdc2DcukspOT6A_ypN3NA/view?usp=sharing)

---

## Why I Chose Consus

I chose **Consus** because it is a real Y Combinator startup working on secure and compliant AI infrastructure for aerospace and defense organizations.

What interested me was the problem that comes **before** a company uses such infrastructure:

> Is the company itself ready from a compliance and security point of view?

That question became the idea for my MCP project.

## What Consus Does

Consus focuses on secure AI infrastructure for sensitive aerospace and defense workloads. Its platform deals with areas such as ITAR, FedRAMP High, CUI, access restrictions, auditing, and secure infrastructure boundaries.

My project does **not** copy or replace Consus. Instead, it works as a **customer-side compliance readiness layer** that can help an organization prepare before using secure AI infrastructure.

| Consus | My Project |
|---|---|
| Secure AI infrastructure | Compliance readiness |
| Runtime security | Pre-deployment assessment |
| Infrastructure platform | Policy analysis |
| Secure deployment environment | Gap detection and remediation |

---

## What I Built

I built a **Compliance Readiness MCP Server** that can:

- Read company policies in PDF, DOCX, TXT and Markdown
- Extract and chunk policy content
- Use RAG to find relevant evidence
- Compare policies with compliance requirements
- Identify `MATCH`, `PARTIAL`, and `MISMATCH`
- Generate remediation suggestions
- Create and assign compliance tasks
- Re-check updated policies
- Generate compliance and readiness reports

---

## How It Works

text
Company Policies
       ↓
Document Extraction
       ↓
Chunking + RAG
       ↓
Compliance Analysis
       ↓
MATCH / PARTIAL / MISMATCH
       ↓
Remediation Tasks
       ↓
Human Updates Policy
       ↓
Re-check
       ↓
Final Readiness Report
       ↓
Human Approval

The AI helps with analysis and recommendations, but the final policy changes and approval remain with humans.
RAG
Instead of sending complete policy documents to the LLM, the system retrieves only the most relevant sections.
Metric	Value
Full repository	5,428 tokens
Retrieved chunks	591 tokens
Tokens saved	4,837
Context reduction	89.11%


This makes the compliance analysis more focused and reduces unnecessary context.
MCP Tools
Tool	Purpose
register_company	Register a company
scan_company_documents	Find policy documents
store_company_documents	Process and index documents
analyze_compliance	Analyze compliance
get_compliance_suggestions	Suggest remediation
create_compliance_tasks	Create tasks
assign_compliance_task	Assign tasks
update_task_status	Update task status
recheck_requirement	Re-check a requirement
generate_final_readiness_report	Generate final report


Reports
The system generates two main reports:
1. Compliance Gap Report – shows missing controls, findings and recommended actions.
2. Final Readiness Report – shows the final compliance status, resolved tasks and human sign-off section.
Tech Stack
Technology	Purpose
Python	Backend
FastMCP	MCP Server
SQLite	Database
RAG + TF-IDF	Policy retrieval
Ollama	Local LLM evaluation
pypdf	PDF processing
python-docx	DOCX processing
Pytest	Testing
ReportLab	PDF reports


Folder Structure
compliance-readiness-mcp/
│
├── data/          # Policies and generated reports
├── docs/          # Documentation
├── scripts/       # Demo and utility scripts
├── src/
│   ├── database/  # SQLite database
│   ├── llm/       # LLM evaluation
│   ├── rag/       # RAG pipeline
│   └── tools/     # MCP tools and reports
├── tests/         # Automated tests
├── server.py      # MCP server
├── requirements.txt
└── README.md

Running the Project
git clone https://github.com/gbyGaurav/compliance-readiness-mcp.git
cd compliance-readiness-mcp
uv pip install -r requirements.txt

Run the tests:
python -m pytest tests -v

Run the demo:
python scripts/run_demo.py

Final Idea
The idea is simple:
Before deploying sensitive AI workloads, first check whether the organization is actually ready.

Consus focuses on secure AI infrastructure, while this project focuses on the customer's compliance preparation before deployment.
Disclaimer
This is an independent educational/prototype project inspired by the publicly described problem space of Consus. It is not an official Consus product and does not use proprietary Consus data or documents.
Author
Gaurav Deore
AI/ML & Data Science Engineer
GitHub: https://github.com/gbyGaurav
