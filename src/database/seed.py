"""
Seed script to populate representative Consus requirements into SQLite.
"""

from pathlib import Path
from typing import List
from src.config import CONSUS_REQ_DATA_DIR
from src.database.models import ComplianceRequirement
from src.database.db import db_manager


def seed_requirements():
    """
    Parses representative Consus requirements from markdown files and stores them in SQLite.
    """
    reqs: List[ComplianceRequirement] = [
        ComplianceRequirement(
            requirement_id="CONSUS-DATA-001",
            title="US-Only Sovereign Geographic Boundary & Data Isolation",
            category="Data Boundary and Sovereignty",
            severity="Critical",
            description="All customer data, model training datasets, inference request payloads, generated tokens, embeddings, vector indices, and system backups must remain strictly confined to approved US sovereign boundaries and FedRAMP High / DoD IL4+ authorized cloud regions.",
            mandatory_controls=[
                "Strict prohibition of cross-border data replication or backup storage outside US sovereign partitions.",
                "Network perimeter isolation rejecting non-US ingress/egress for AI workloads.",
                "Formal policy commitment to sovereign boundary enforcement.",
            ],
            verification_criteria=[
                "Policy must explicitly designate US sovereign storage boundaries.",
                "Policy must explicitly prohibit global replication or cross-border transit of defense and CUI assets.",
            ],
        ),
        ComplianceRequirement(
            requirement_id="CONSUS-ENC-001",
            title="Cryptographic Protection in Transit and at Rest",
            category="Cryptography and Encryption",
            severity="High",
            description="All customer datasets, model artifacts, embeddings, query logs, and communication channels processing sensitive defense information must enforce modern cryptographic controls aligned with FIPS 140-2/3 validation.",
            mandatory_controls=[
                "Encryption at rest using AES-256 for all persistent volumes, buckets, and databases.",
                "Encryption in transit enforcing TLS 1.2 or TLS 1.3 with forward secrecy.",
                "Secure Key Management Service (KMS) or HSM with annual key rotation.",
            ],
            verification_criteria=[
                "Policy must mandate AES-256 for data at rest.",
                "Policy must enforce TLS 1.2+ for in-transit network communication.",
                "Policy must specify KMS-managed key rotation.",
            ],
        ),
        ComplianceRequirement(
            requirement_id="CONSUS-IAM-001",
            title="Granular Role-Based Access Control (RBAC) and US-Person Access Enforcement",
            category="Identity and Access Management",
            severity="High",
            description="Access to defense-related AI models, training pipelines, fine-tuned weights, and inference APIs must be restricted based on strict principle of least privilege, granular role-based access control (RBAC), multi-factor authentication (MFA), and verifiable US-Person status.",
            mandatory_controls=[
                "Granular role-based access control (RBAC) with least-privilege scoping (no broad shared access).",
                "Mandatory US-Person citizenship or lawful permanent resident verification for defense/ITAR workloads.",
                "Universal phishing-resistant Multi-Factor Authentication (MFA).",
            ],
            verification_criteria=[
                "Policy must enforce fine-grained RBAC and least-privilege scoping.",
                "Policy must require US-Person status verification for defense/ITAR data access.",
                "Policy must mandate MFA across all access points.",
            ],
        ),
        ComplianceRequirement(
            requirement_id="CONSUS-LOG-001",
            title="Comprehensive Immutable Audit Logging and Centralized Telemetry",
            category="Audit Logging and Monitoring",
            severity="High",
            description="All administrative actions, security event telemetry, authentication attempts, privilege elevations, policy modifications, and AI inference requests must be continuously logged into tamper-evident, write-once storage and retained for minimum 365 calendar days.",
            mandatory_controls=[
                "Continuous logging of model inference queries, administrative privilege elevations, and authentications.",
                "Immutable, write-once-read-many (WORM) storage with cryptographic tamper-evidence.",
                "Minimum 365 calendar days (1 year) retention SLA.",
            ],
            verification_criteria=[
                "Policy must cover model inference calls, privilege elevations, and authentication events.",
                "Policy must mandate write-once or tamper-evident log storage.",
                "Policy must mandate minimum 1-year (365 days) retention.",
            ],
        ),
        ComplianceRequirement(
            requirement_id="CONSUS-IR-001",
            title="Security Incident Response, Containment, and Notification SLA",
            category="Incident Response",
            severity="High",
            description="Customers utilizing compliant AI infrastructure must maintain a formally documented incident response plan (IRP) with defined operational roles, active threat containment capabilities, forensic preservation processes, and timely external notification thresholds.",
            mandatory_controls=[
                "Documented incident response plan with chartered roles (Incident Commander, Lead Analyst).",
                "Immediate containment and isolation workflows for compromised hosts and credentials.",
                "Customer and partner notification SLA within 72 hours of confirmed breach.",
            ],
            verification_criteria=[
                "Policy must define incident response roles and severity levels.",
                "Policy must provide isolation and containment workflows.",
                "Policy must commit to notification within 72 hours following breach confirmation.",
            ],
        ),
    ]

    for req in reqs:
        db_manager.upsert_requirement(req)

    import sys
    print(f"Successfully seeded {len(reqs)} representative Consus requirements into SQLite.", file=sys.stderr)


if __name__ == "__main__":
    seed_requirements()
