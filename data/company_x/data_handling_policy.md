# Company X Data Handling, Storage, and Boundary Policy (v1)

**Document ID:** CX-POL-DAT-001  
**Version:** 1.0  
**Effective Date:** 2026-01-10  
**Owner:** Data Governance Committee, Company X (Fictional Customer)

---

## 1. Data Classification Scheme
Company X classifies data into three tiers:
- **Public:** Marketing assets, public documentation.
- **Internal:** General business communications, product roadmaps.
- **Confidential:** Customer transaction details, proprietary algorithms, and source code.

## 2. Storage and Data Retention
- Production data is retained for three years unless contractual terms require earlier disposal.
- Secure deletion requires cryptographic erasure or physical media destruction compliant with NIST 800-88.

## 3. Geographic Hosting and Cloud Backup Policy
- Company X utilizes commercial hyperscaler cloud environments (AWS, GCP, Azure).
- **Global Replication Permitted:** To guarantee 99.99% high availability and resilient disaster recovery, primary production datasets, object storage buckets, and database snapshots may be replicated globally across multiple international availability zones and regions (including US East, EU West, and Asia-Pacific).
- Data sovereignty restrictions are currently managed on an ad-hoc basis upon bespoke customer contract request rather than as a strict baseline architecture constraint.
- No mandatory restriction exists preventing sensitive model training or inference payloads from traversing international data networks.
