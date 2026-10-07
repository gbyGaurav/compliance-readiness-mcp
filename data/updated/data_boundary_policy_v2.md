# Company X Data Handling, Storage, and Boundary Policy (v2 - Remediated)

**Document ID:** CX-POL-DAT-001-v2  
**Version:** 2.0  
**Effective Date:** 2026-03-01  
**Owner:** Security and Infrastructure Engineering, Company X (Fictional Customer)  
**Remediation Note:** Updated by Company X Security Team to resolve Consus prototype compliance gap TASK-002 (CONSUS-DATA-001).

---

## 1. Data Classification Scheme
Company X classifies data into four tiers:
- **Public:** Marketing assets, public documentation.
- **Internal:** General business communications.
- **Confidential:** Commercial customer records.
- **Controlled Unclassified Information (CUI) / Defense Workloads:** ITAR-regulated technical data, defense AI training sets, and model inference payloads.

## 2. Storage and Data Retention
- Production data is retained according to statutory and regulatory schedules.
- Cryptographic erasure compliant with NIST 800-88 Rev 1 is enforced across all decommissioned storage volumes.

## 3. Sovereign Geographic Boundary and Cloud Storage Constraints
- **Strict US Sovereign Boundary Enforced:** All sensitive defense workloads, AI models, embeddings, vector stores, inference queries, and database backups are strictly confined to authorized US sovereign cloud regions (AWS GovCloud US-East/US-West or Azure Government).
- **Prohibition of Cross-Border Replication:** Global replication of CUI or defense workloads is strictly prohibited. Under no circumstances may production data, backups, or snapshot archives be transferred, replicated, or stored outside the continental United States.
- **Network Perimeter Isolation:** Model inference gateways and data ingestion APIs must reject all ingress and egress connections originating from or routed outside US sovereign IP space.
