# Company X Identity and Access Control Policy (v2 - Remediated)

**Document ID:** CX-POL-IAM-001-v2  
**Version:** 2.0  
**Effective Date:** 2026-03-01  
**Owner:** Security Architecture Team, Company X (Fictional Customer)  
**Remediation Note:** Updated by Company X Security Team to resolve Consus prototype compliance gap TASK-001 (CONSUS-IAM-001).

---

## 1. Overview and Intent
This policy defines identity verification, granular role-based access control (RBAC), and export-controlled data access constraints across Company X infrastructure and AI workloads.

## 2. Granular Role-Based Access Control (RBAC) & Least Privilege
- Access permissions are strictly managed through fine-grained, role-based access control (RBAC) mapped directly to job function and least-privilege principles.
- Broad group-level shared read permissions are revoked. Access to AI development environments, models, weights, and embeddings requires explicitly documented role authorization.
- Shared administrative credentials are prohibited. Temporary elevated access requires just-in-time (JIT) credential issuance with automated expiration.

## 3. Mandatory US-Person Verification for Defense & CUI Workloads
- In full compliance with ITAR (22 CFR § 120.15), all engineers, operators, and contractors granted access to defense AI systems, training pipelines, or CUI environments must have verified US-Person status (US Citizen or lawful permanent resident / Green Card holder).
- Identity verification records are validated prior to provisioning and re-certified semi-annually.

## 4. Multi-Factor Authentication (MFA)
- Phishing-resistant FIDO2/WebAuthn hardware MFA is mandatory across all user accounts, production consoles, and developer CLI tools. Single-factor access is systematically blocked.
