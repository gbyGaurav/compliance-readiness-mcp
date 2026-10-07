# Company X System and Security Event Logging Policy (v1)

**Document ID:** CX-POL-LOG-001  
**Version:** 1.0  
**Effective Date:** 2026-01-25  
**Owner:** IT Infrastructure and DevOps, Company X (Fictional Customer)

---

## 1. Scope
This policy applies to operating system logging, web server access logging, and database transaction tracking across Company X environments.

## 2. Currently Captured Events
- Successful and failed corporate SSO login attempts.
- HTTP 500-series server error traces and exception dumps.
- Periodic deployment scripts and git commit history on master branches.

## 3. Log Storage and Retention
- System logs are aggregated locally on host servers and shipped weekly to a central cloud log storage bucket.
- Logs are retained for a default duration of 90 days, after which automated lifecycle policies delete older archives to optimize storage costs.

## 4. Current Logging Shortfalls
- Real-time logging of individual model inference queries, prompt payloads, and AI API transactions is not currently enabled due to telemetry volume concerns.
- Administrative privilege escalations (e.g., sudo invocation, cloud IAM role assumptions) are only captured in raw host syslog files without central write-once protection or tamper-evident cryptographic sealing.
- Retention is 90 days, which is less than the 1-year (365 days) historical compliance retention demanded by stringent federal defense frameworks.
