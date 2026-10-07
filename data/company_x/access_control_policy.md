# Company X Identity and Access Control Policy (v1)

**Document ID:** CX-POL-IAM-001  
**Version:** 1.0  
**Effective Date:** 2026-01-20  
**Owner:** IT Infrastructure Team, Company X (Fictional Customer)

---

## 1. Overview and Intent
This policy defines the user identification, password complexity, and high-level access grant principles across corporate networks and software applications.

## 2. User Authentication and Credentials
- All users must authenticate via corporate Single Sign-On (SSO) or local credentials where SSO is unavailable.
- Passwords must be at least 12 characters in length and include uppercase letters, numbers, and symbols. Passwords expire every 90 days.
- Multi-factor authentication (MFA) is enabled for email accounts and remote VPN access.

## 3. General Access Provisioning
- Access is provisioned based on departmental group membership (e.g., Engineering, Marketing, Operations).
- Broad shared read access is granted to shared engineering folders to foster cross-team collaboration.
- Privilege changes are requested via email or ticketing systems and reviewed periodically during managerial reviews.

## 4. Current Limitations & Gaps
- Fine-grained Role-Based Access Control (RBAC) with specific resource-level constraints is not fully implemented across AI development sandboxes.
- Nationality or sovereign citizen-status verification (e.g., US-Person verification for defense/ITAR export-controlled workloads) is not formally tracked or enforced in current identity directory attributes.
- Elevated administrator privileges are shared across senior systems engineers without strict task-scoped credential issuance.
