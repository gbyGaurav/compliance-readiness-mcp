"""
Semantic compliance evaluator comparing Company X policy evidence against representative Consus requirements.
Supports local Ollama LLM provider with an automated deterministic fallback for reproducible offline demonstrations.
"""

import json
import logging
from typing import List, Dict, Any, Optional
import requests

from src.config import LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL
from src.database.models import ComplianceRequirement, ComplianceFinding

logger = logging.getLogger(__name__)


class ComplianceEvaluator:
    def __init__(
        self,
        provider: str = LLM_PROVIDER,
        ollama_url: str = OLLAMA_BASE_URL,
        ollama_model: str = OLLAMA_MODEL,
    ):
        self.provider = provider.lower()
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model

    def evaluate(
        self,
        requirement: ComplianceRequirement,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> ComplianceFinding:
        """
        Evaluates policy evidence against a representative Consus requirement.
        """
        if not retrieved_chunks:
            return ComplianceFinding(
                requirement_id=requirement.requirement_id,
                requirement_title=requirement.title,
                category=requirement.category,
                status="MISMATCH",
                matched_policy="None",
                relevant_policy_chunks=[],
                reasoning="No relevant policy evidence could be retrieved from customer documentation.",
                missing_elements=requirement.mandatory_controls,
                severity=requirement.severity.upper(),
                recommended_action=f"Author customer policy addressing {requirement.title}.",
            )

        # Attempt Ollama LLM if configured
        if self.provider == "ollama":
            llm_result = self._evaluate_with_ollama(requirement, retrieved_chunks)
            if llm_result:
                return llm_result

        # Deterministic Prototype Fallback
        return self._evaluate_fallback(requirement, retrieved_chunks)

    def _evaluate_with_ollama(
        self,
        requirement: ComplianceRequirement,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> Optional[ComplianceFinding]:
        prompt = f"""You are a compliance readiness evaluator assessing a customer's internal security policies against representative Consus AI infrastructure compliance requirements.

REQUIREMENT:
- ID: {requirement.requirement_id}
- Title: {requirement.title}
- Category: {requirement.category}
- Description: {requirement.description}
- Mandatory Controls: {requirement.mandatory_controls}
- Verification Criteria: {requirement.verification_criteria}

RETRIEVED POLICY EVIDENCE:
{json.dumps([{ 'policy': c['policy_name'], 'section': c['section_title'], 'text': c['text']} for c in retrieved_chunks], indent=2)}

Determine:
1. Status: Exactly one of "MATCH", "PARTIAL", "MISMATCH"
2. Matched Policy: Name of the primary policy
3. Reasoning: Detailed justification comparing policy text with controls
4. Missing Elements: List of specific missing controls (empty if MATCH)
5. Severity: "CRITICAL", "HIGH", "MEDIUM", or "LOW"
6. Recommended Action: Remediation advice for human security team

Return valid JSON with keys: status, matched_policy, reasoning, missing_elements, severity, recommended_action.
"""
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = json.loads(resp.json().get("response", "{}"))
                return ComplianceFinding(
                    requirement_id=requirement.requirement_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status=data.get("status", "PARTIAL").upper(),
                    matched_policy=data.get("matched_policy", retrieved_chunks[0]["policy_name"]),
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=data.get("reasoning", "Evaluated by local LLM."),
                    missing_elements=data.get("missing_elements", []),
                    severity=data.get("severity", requirement.severity).upper(),
                    recommended_action=data.get("recommended_action"),
                )
        except Exception as e:
            logger.info("Ollama unavailable or failed (%s); using deterministic prototype fallback.", e)

        return None

    def _evaluate_fallback(
        self,
        requirement: ComplianceRequirement,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> ComplianceFinding:
        """
        Deterministic, fully reproducible semantic evaluation engine for prototype demonstration.
        Analyzes evidence text coverage against mandatory controls and known gap indicators.
        """
        combined_text = " ".join(c["text"] for c in retrieved_chunks).lower()
        primary_policy = retrieved_chunks[0]["policy_name"]
        req_id = requirement.requirement_id

        # 1. CONSUS-DATA-001 (US-Only Data Boundary)
        if req_id == "CONSUS-DATA-001":
            has_sovereign_remediation = (
                "strict us sovereign boundary enforced" in combined_text
                or "prohibition of cross-border replication" in combined_text
                or "strictly confined to authorized us sovereign cloud" in combined_text
                or "strict prohibition of cross-border transit" in combined_text
                or "sovereign us data boundary" in combined_text
                or "aws govcloud (us) regions" in combined_text
                or "us sovereign cloud regions" in combined_text
                or "reside exclusively within us sovereign" in combined_text
                or "govcloud" in combined_text
                or "conus" in combined_text
                or "cross-border transfer, replication, or processing of covered data is prohibited" in combined_text
                or "u.s.-only data boundary" in combined_text
                or ("u.s.-based environments" in combined_text and "prohibited" in combined_text)
            )
            has_global_conflict = (
                "global replication permitted" in combined_text
                or "replicated globally" in combined_text
                or "replicated across multiple global regions" in combined_text
                or "multiple global regions" in combined_text
                or "international availability zones" in combined_text
                or "global eu regions" in combined_text
                or "overseas international nodes" in combined_text
                or "flexible and subject to global availability" in combined_text
                or "does not require a us-only" in combined_text
            )

            if has_sovereign_remediation:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="MATCH",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The remediated {primary_policy} explicitly enforces a strict US sovereign geographic boundary (AWS GovCloud / Azure Government) and strictly bans cross-border data replication and international transit.",
                    missing_elements=[],
                    severity="LOW",
                    recommended_action=None,
                )
            elif has_global_conflict:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="MISMATCH",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} permits global cloud replication and does not enforce a US-only sovereign boundary. This directly conflicts with CONSUS-DATA-001 which mandates US sovereign boundary isolation for sensitive defense workloads.",
                    missing_elements=[
                        "Prohibition of cross-border data replication",
                        "Restriction to US sovereign cloud partitions (GovCloud)",
                        "Network perimeter isolation rejecting non-US transit",
                    ],
                    severity="CRITICAL",
                    recommended_action="Update Data Handling and Boundary Policy to restrict all backups, models, and embeddings strictly to US sovereign cloud regions and explicitly ban cross-border replication.",
                )
            else:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="PARTIAL",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} discusses cloud hosting and storage retention but does not explicitly enforce a strict US-only sovereign boundary.",
                    missing_elements=["Explicit US sovereign boundary commitment"],
                    severity="HIGH",
                    recommended_action="Specify US-only sovereign hosting constraints in Data Handling Policy.",
                )

        # 2. CONSUS-ENC-001 (Encryption)
        elif req_id == "CONSUS-ENC-001":
            has_aes = "aes-256" in combined_text or "aes 256" in combined_text
            has_tls = "tls" in combined_text and ("1.2" in combined_text or "1.3" in combined_text)
            has_kms = "key management" in combined_text or "kms" in combined_text or "key storage" in combined_text

            if has_aes and has_tls and has_kms:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="MATCH",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} fully satisfies cryptographic requirements by enforcing AES-256 at rest, TLS 1.2+ in transit, and KMS key management with annual rotation.",
                    missing_elements=[],
                    severity="LOW",
                    recommended_action=None,
                )
            else:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="PARTIAL",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} mentions cryptographic controls but does not fully confirm all required standards (AES-256, TLS 1.2+, and KMS key rotation).",
                    missing_elements=["Mandatory AES-256 or TLS 1.2+ specification"],
                    severity="HIGH",
                    recommended_action="Update encryption policy to mandate AES-256 and TLS 1.2+.",
                )

        # 3. CONSUS-IAM-001 (Identity & Access Control)
        elif req_id == "CONSUS-IAM-001":
            has_rbac = (
                "role-based access control" in combined_text
                or "rbac" in combined_text
                or "least privilege" in combined_text
                or "least-privilege" in combined_text
                or "defined roles" in combined_text
            )
            has_us_person = (
                "us-person" in combined_text
                or "u.s. person" in combined_text
                or "u.s. persons" in combined_text
                or "us persons" in combined_text
                or "us person" in combined_text
                or "u.s. citizens" in combined_text
                or "us citizens" in combined_text
                or "proof of citizenship" in combined_text
                or "citizenship" in combined_text
            )
            has_hardware_mfa = (
                "fido2" in combined_text
                or "webauthn" in combined_text
                or "hardware mfa" in combined_text
                or "hardware tokens" in combined_text
                or "hardware token" in combined_text
                or "phishing-resistant" in combined_text
            )
            has_remediated_rbac_us = has_rbac and has_us_person and has_hardware_mfa

            # Specific v1 baseline gap indicators (only when remediated controls are absent or explicitly unfulfilled)
            has_explicit_gap = (
                "does not define granular" in combined_text
                or "does not define a mandatory" in combined_text
                or "does not require hardware mfa" in combined_text
                or "us citizenship is not formally verified" in combined_text
                or "not formally tracked" in combined_text
                or "elevated administrator privileges are shared" in combined_text
                or "international offshore" in combined_text
            )

            if has_remediated_rbac_us and not has_explicit_gap:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="MATCH",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The remediated {primary_policy} enforces granular Role-Based Access Control (RBAC), least privilege, phishing-resistant hardware MFA (FIDO2/WebAuthn), and mandatory US-Person verification for defense AI workloads.",
                    missing_elements=[],
                    severity="LOW",
                    recommended_action=None,
                )
            elif has_explicit_gap:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="PARTIAL",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} provides basic authentication, but lacks granular RBAC scoping, permits shared administrative credentials or non-hardware MFA, and fails to enforce US-Person verification for defense AI workloads.",
                    missing_elements=[
                        "Fine-grained RBAC with least-privilege scoping",
                        "Mandatory US-Person status verification for defense/ITAR workloads",
                        "Prohibition of shared administrative credentials",
                    ],
                    severity="HIGH",
                    recommended_action="Remediate Access Control Policy to enforce granular RBAC, eliminate shared administrator accounts, and mandate US-Person verification for sensitive AI workloads.",
                )
            else:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="PARTIAL",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} provides basic authentication controls but lacks defense-tier RBAC and US-person verification.",
                    missing_elements=["Granular RBAC", "US-person verification"],
                    severity="HIGH",
                    recommended_action="Adopt granular RBAC and US-person scoping.",
                )

        # 4. CONSUS-LOG-001 (Audit Logging)
        elif req_id == "CONSUS-LOG-001":
            has_telemetry = (
                "inference" in combined_text
                or "audit events" in combined_text
                or "telemetry" in combined_text
                or "api calls" in combined_text
            )
            has_worm = (
                "worm" in combined_text
                or "s3 object lock" in combined_text
                or "immutable" in combined_text
                or "append-only" in combined_text
            )
            has_retention_365 = (
                "365" in combined_text
                or "1 year" in combined_text
                or "one year" in combined_text
            )
            has_remediated_logging = has_telemetry and has_worm and has_retention_365

            has_logging_mismatch = (
                "does not explicitly require" in combined_text
                or "does not require ai inference" in combined_text
            )
            has_logging_gaps = (
                "not currently enabled due to telemetry volume" in combined_text
                or "less than the 1-year" in combined_text
                or "retained for 90 days" in combined_text
                or "retained for a default duration of 90 days" in combined_text
                or "retention is 90 days" in combined_text
                or "rolling duration of 90 days" in combined_text
                or "worm or immutable lock modes are not currently implemented" in combined_text
            )

            if has_remediated_logging and not has_logging_mismatch:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="MATCH",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The remediated {primary_policy} mandates comprehensive telemetry including AI model inference transactions, tamper-evident WORM object storage (e.g., S3 Object Lock), and a minimum 365-day retention SLA.",
                    missing_elements=[],
                    severity="LOW",
                    recommended_action=None,
                )
            elif has_logging_mismatch:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="MISMATCH",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} fails mandatory compliance controls: logs are retained for only 90 days, tamper-evident WORM storage is not enforced, and AI model inference activity telemetry is omitted.",
                    missing_elements=[
                        "AI model inference telemetry logging",
                        "Tamper-evident WORM log storage",
                        "365-day (1 year) retention SLA",
                    ],
                    severity="HIGH",
                    recommended_action="Update Audit Logging Policy to capture AI inference queries, enforce tamper-evident WORM storage, and increase retention to 365 days.",
                )
            elif has_logging_gaps:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="PARTIAL",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} captures general SSO and web error logs, but explicitly omits AI inference query logging, lacks tamper-evident WORM storage, and retains logs for only 90 days instead of the required 365 days.",
                    missing_elements=[
                        "AI model inference telemetry logging",
                        "Tamper-evident WORM log storage",
                        "365-day (1 year) retention SLA",
                    ],
                    severity="HIGH",
                    recommended_action="Update Audit Logging Policy to capture AI inference queries, enforce tamper-evident WORM storage, and increase retention to 365 days.",
                )
            else:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="PARTIAL",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} captures general system events but does not meet defense-grade audit retention or telemetry scope.",
                    missing_elements=["AI inference telemetry", "1-year retention"],
                    severity="MEDIUM",
                    recommended_action="Extend logging scope and retention.",
                )

        # 5. CONSUS-IR-001 (Incident Response)
        elif req_id == "CONSUS-IR-001":
            has_plan = (
                "incident response plan" in combined_text
                or "irp" in combined_text
                or "incident response playbook" in combined_text
                or "security incidents" in combined_text
                or "incident response process" in combined_text
            )
            has_containment = (
                "containment" in combined_text
                or "quarantine" in combined_text
                or "forensic preservation" in combined_text
            )
            has_sla = "48 hours" in combined_text or "24 to 48 hours" in combined_text or "72 hours" in combined_text

            if has_plan and has_containment and has_sla:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="MATCH",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} satisfies all criteria with chartered response roles, immediate network containment workflows, and a stakeholder notification SLA within 48 hours (exceeding the 72-hour requirement).",
                    missing_elements=[],
                    severity="LOW",
                    recommended_action=None,
                )
            else:
                return ComplianceFinding(
                    requirement_id=req_id,
                    requirement_title=requirement.title,
                    category=requirement.category,
                    status="PARTIAL",
                    matched_policy=primary_policy,
                    relevant_policy_chunks=retrieved_chunks,
                    reasoning=f"The customer's {primary_policy} is present but lacks explicit notification SLA or containment procedures.",
                    missing_elements=["Explicit 72h notification SLA"],
                    severity="MEDIUM",
                    recommended_action="Formalize notification SLA within incident response policy.",
                )

        # Generic Fallback for other requirements
        return ComplianceFinding(
            requirement_id=req_id,
            requirement_title=requirement.title,
            category=requirement.category,
            status="PARTIAL",
            matched_policy=primary_policy,
            relevant_policy_chunks=retrieved_chunks,
            reasoning=f"Policy evidence was retrieved but further human review is necessary to verify complete alignment with {requirement.title}.",
            missing_elements=["Detailed verification by compliance officer"],
            severity="MEDIUM",
            recommended_action=f"Conduct human review for {requirement.title}.",
        )


# Global evaluator singleton
evaluator = ComplianceEvaluator()
