# Company X Cryptographic Standards and Encryption Policy

**Document ID:** CX-POL-ENC-001  
**Version:** 1.2  
**Effective Date:** 2026-02-01  
**Owner:** Security Architecture Team, Company X (Fictional Customer)

---

## 1. Scope and Objective
This document outlines the cryptographic standards enforced across all Company X production systems, customer data repositories, and transmission channels.

## 2. Encryption at Rest
- **Cryptographic Standard:** All databases, object storage volumes, virtual machine disks, and persistent application caches storing customer data or confidential business information must be encrypted at rest using AES-256 (Advanced Encryption Standard with 256-bit keys).
- **Key Storage:** Master cryptographic keys must be stored in hardware security modules (HSM) or dedicated cloud Key Management Services (KMS).
- **Key Rotation:** Data encryption keys must be rotated at minimum once every 365 days. Automatic KMS key rotation must be enabled by default.

## 3. Encryption in Transit
- **Transport Protocols:** All external and internal communications carrying sensitive, confidential, or production data must utilize Transport Layer Security (TLS) version 1.2 or TLS version 1.3.
- **Prohibited Protocols:** Deprecated protocols including SSLv3, TLS 1.0, and TLS 1.1, along with unencrypted protocols (HTTP, Telnet, FTP), are strictly prohibited.
- **Cipher Suites:** Only strong cipher suites supporting Forward Secrecy (ECDHE-RSA-AES128-GCM-SHA256, ECDHE-RSA-AES256-GCM-SHA384, ChaCha20-Poly1305) are permitted on public and private endpoints.

## 4. Key Management and Access Controls
Cryptographic key administration duties must be separated from operational system administrators. Multi-party authorization is required for key export or destruction activities. Key access logs are maintained and inspected quarterly.
