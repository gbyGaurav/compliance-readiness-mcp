# Company X Security Incident Response Plan

**Document ID:** CX-POL-IR-001  
**Version:** 2.0  
**Effective Date:** 2026-02-15  
**Owner:** Security Operations Center (SOC), Company X (Fictional Customer)

---

## 1. Objective and Activation
This Incident Response Plan (IRP) provides operational procedures for identifying, analyzing, containing, eradicating, and recovering from cybersecurity incidents threatening Company X assets or customer information.

## 2. Incident Response Team Structure
- **Incident Commander:** Directs tactical triage, work assignments, and executive escalation.
- **Lead Security Analyst:** Executes forensic analysis, endpoint containment, and threat neutralization.
- **Legal and Communications Officer:** Manages customer disclosure notifications and regulatory reporting.

## 3. Incident Severity Levels
- **Severity 1 (Critical):** Active breach of production data, unauthorized access to sensitive keys, or widespread service compromise.
- **Severity 2 (High):** Targeted attack with contained impact, credential compromise of non-privileged employee.
- **Severity 3 (Medium/Low):** Isolated malware on employee endpoint, blocked suspicious scanning.

## 4. Response Workflow and Notification SLA
- **Detection & Triage:** Security telemetry is monitored 24/7. High-severity alerts must be acknowledged within 15 minutes.
- **Containment:** Affected nodes are quarantined from network segments immediately upon validation.
- **Customer Notification:** In the event of confirmed unauthorized access or exposure of customer data, affected stakeholders and partners must be notified in writing within 24 to 48 hours, well within federal and commercial SLA thresholds.
- **Post-Incident Review:** Root-cause analysis (RCA) must be published within 5 business days of incident closure.
