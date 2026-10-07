"""
PDF Report Generator for Consus Compliance Operations MCP.
Generates:
1. Compliance Gap Report PDF (pre-remediation gap analysis)
2. Final Compliance Readiness Report PDF (post-remediation verification & sign-off)
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from src.config import REPORTS_DIR


def _sanitize(text: str) -> str:
    """Sanitizes text to avoid Latin-1 / UTF-8 codec errors in standard fpdf fonts."""
    if not text:
        return ""
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "*",
        "\u2026": "...",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text.encode("ascii", "replace").decode("ascii")


class CompliancePDF(FPDF):
    def __init__(self, title_text: str, subtitle_text: str):
        super().__init__()
        self.title_text = title_text
        self.subtitle_text = subtitle_text

    def header(self):
        self.set_font("helvetica", "B", 14)
        self.set_text_color(24, 43, 73)  # Consus navy
        self.cell(0, 8, _sanitize(self.title_text), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        self.set_font("helvetica", "I", 9)
        self.set_text_color(100, 110, 120)
        self.cell(0, 5, _sanitize(self.subtitle_text), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        self.ln(2)
        self.set_draw_color(200, 205, 215)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(130, 140, 150)
        self.cell(
            0,
            10,
            f"Page {self.page_no()}/{{nb}} | Consus Pre-Assessment Prototype | Human Review Required",
            align="C",
        )


def generate_gap_report_pdf(
    company_id: str,
    findings: List[Dict[str, Any]],
    summary: Dict[str, Any],
    output_path: Optional[Path] = None,
) -> str:
    """
    Generates a PDF Compliance Gap Report detailing missing controls and recommended remediation.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target_file = REPORTS_DIR / f"compliance_gap_report_{company_id}_{timestamp_str}.pdf"
    else:
        target_file = Path(output_path)

    pdf = CompliancePDF(
        title_text="CONSUS COMPLIANCE GAP ASSESSMENT REPORT",
        subtitle_text=f"Target: {company_id.upper()} | Aerospace & Defense Compliant AI Pre-Assessment",
    )
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    # Assessment Meta & Overview Box
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.set_fill_color(245, 247, 250)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(30, 40, 50)
    pdf.cell(0, 7, f"Assessment Generated: {now_str}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(3)

    # Metrics Summary Cards
    pdf.set_font("helvetica", "B", 10)
    col_w = 47
    pdf.cell(col_w, 7, f"Total: {summary.get('total_requirements', 0)}", border=1, align="C")
    pdf.set_text_color(40, 167, 69)  # Green
    pdf.cell(col_w, 7, f"MATCH: {summary.get('match', 0)}", border=1, align="C")
    pdf.set_text_color(255, 140, 0)  # Orange
    pdf.cell(col_w, 7, f"PARTIAL: {summary.get('partial', 0)}", border=1, align="C")
    pdf.set_text_color(220, 53, 69)  # Red
    pdf.cell(col_w, 7, f"MISMATCH: {summary.get('mismatch', 0)}", border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(7)

    # Detailed Findings Section
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(24, 43, 73)
    pdf.cell(0, 7, "Requirement Gap Analysis & Findings", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    for f in findings:
        status = f.get("status", "UNKNOWN")
        req_id = f.get("requirement_id", "")
        title = f.get("requirement_title", "")
        matched_policy = f.get("matched_policy", "None")
        severity = f.get("severity", "MEDIUM")
        reasoning = f.get("reasoning", "")
        missing = f.get("missing_elements", [])
        action = f.get("recommended_action", "")

        # Header for finding
        pdf.set_font("helvetica", "B", 10)
        if status == "MATCH":
            pdf.set_text_color(40, 167, 69)
        elif status == "PARTIAL":
            pdf.set_text_color(255, 140, 0)
        else:
            pdf.set_text_color(220, 53, 69)

        pdf.cell(0, 6, _sanitize(f"[{status}] {req_id}: {title} (Severity: {severity})"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(0, 5, _sanitize(f"Evidence Policy: {matched_policy}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Reasoning
        pdf.set_font("helvetica", "I", 8.5)
        pdf.multi_cell(0, 4.5, _sanitize(f"Finding: {reasoning}"))

        if missing and status != "MATCH":
            pdf.set_font("helvetica", "B", 8.5)
            pdf.set_text_color(180, 40, 40)
            pdf.cell(0, 5, "Missing Mandatory Elements:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("helvetica", "", 8.5)
            pdf.set_text_color(50, 50, 50)
            for m in missing:
                pdf.cell(0, 4.5, _sanitize(f"  * {m}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if action and status != "MATCH":
            pdf.set_font("helvetica", "B", 8.5)
            pdf.set_text_color(30, 90, 150)
            pdf.multi_cell(0, 4.5, _sanitize(f"Recommended Action: {action}"))

        pdf.ln(3)

    # Governance Notice
    pdf.ln(4)
    pdf.set_fill_color(254, 243, 205)  # Amber warning background
    pdf.set_draw_color(255, 238, 186)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(133, 100, 4)
    pdf.cell(0, 6, "Human Governance Notice", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.set_font("helvetica", "", 8)
    notice_text = (
        "This gap report is generated by the Consus Compliance Operations MCP tool for automated "
        "pre-assessment. It does not replace formal human compliance review or legal audit. "
        "Company policy owners must remediate identified gaps prior to official defense AI authorization."
    )
    pdf.multi_cell(0, 4, _sanitize(notice_text), fill=True)

    pdf.output(str(target_file))
    return str(target_file.resolve())


def generate_final_report_pdf(
    company_id: str,
    report_data: Dict[str, Any],
    output_path: Optional[Path] = None,
) -> str:
    """
    Generates a PDF Final Compliance Readiness Report with human sign-off block.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target_file = REPORTS_DIR / f"final_readiness_report_{company_id}_{timestamp_str}.pdf"
    else:
        target_file = Path(output_path)

    pdf = CompliancePDF(
        title_text="CONSUS FINAL COMPLIANCE READINESS REPORT",
        subtitle_text=f"Customer: {company_id.upper()} | Post-Remediation Verification & Sign-Off",
    )
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    summary = report_data.get("summary", {})
    overall_status = report_data.get("overall_status", "REMEDIATION_REQUIRED")
    report_id = report_data.get("report_id", "REP-FINAL")
    gen_time = report_data.get("generated_at", datetime.now(timezone.utc).isoformat())

    # Overall Status Banner
    is_ready = overall_status == "READY_FOR_HUMAN_REVIEW"
    if is_ready:
        pdf.set_fill_color(212, 237, 218)
        pdf.set_text_color(21, 87, 36)
    else:
        pdf.set_fill_color(248, 215, 218)
        pdf.set_text_color(114, 28, 36)

    pdf.set_font("helvetica", "B", 12)
    banner_text = f"OVERALL READINESS: {overall_status.replace('_', ' ')}"
    pdf.cell(0, 9, _sanitize(banner_text), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, align="C")
    pdf.ln(4)

    # Executive Summary Table
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(24, 43, 73)
    pdf.cell(0, 6, "Executive Assessment Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(95, 6, f"Report ID: {report_id}", border=1)
    pdf.cell(95, 6, f"Date: {gen_time}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(47, 6, f"Total Reqs: {summary.get('total_requirements', 0)}", border=1)
    pdf.cell(47, 6, f"MATCH: {summary.get('match', 0)}", border=1)
    pdf.cell(47, 6, f"Resolved Tasks: {summary.get('resolved_tasks', 0)}", border=1)
    pdf.cell(49, 6, f"Open Tasks: {summary.get('unresolved_tasks', 0)}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    # Assessment Findings Overview
    findings = report_data.get("findings", [])
    if findings:
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(24, 43, 73)
        pdf.cell(0, 6, "Requirement Status Verification", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("helvetica", "B", 8.5)
        pdf.set_fill_color(235, 240, 245)
        pdf.cell(35, 6, "Requirement", border=1, fill=True)
        pdf.cell(25, 6, "Status", border=1, fill=True)
        pdf.cell(60, 6, "Evidence Document", border=1, fill=True)
        pdf.cell(70, 6, "Verification Notes", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("helvetica", "", 8)
        for f in findings:
            req_id = f.get("requirement_id", "")
            status = f.get("status", "")
            pol = f.get("matched_policy", "")
            reason = f.get("reasoning", "")[:50] + "..." if len(f.get("reasoning", "")) > 50 else f.get("reasoning", "")

            pdf.cell(35, 5, _sanitize(req_id), border=1)
            pdf.cell(25, 5, _sanitize(status), border=1)
            pdf.cell(60, 5, _sanitize(pol[:35]), border=1)
            pdf.cell(70, 5, _sanitize(reason), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(6)

    # Human Governance Sign-Off Block
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(24, 43, 73)
    pdf.cell(0, 6, "Human Compliance Governance Certification", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("helvetica", "", 8.5)
    pdf.set_text_color(50, 50, 50)
    signoff_text = (
        "I hereby verify that all representative Consus compliance requirements evaluated above have been "
        "reviewed against internal policies and verified by appropriate human compliance and engineering leads. "
        "This system readiness document is submitted for final administrative authorization."
    )
    pdf.multi_cell(0, 4.5, _sanitize(signoff_text))
    pdf.ln(4)

    # Signature Fields
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(90, 6, "Authorized Compliance Officer: ___________________", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(90, 6, "Date: ___________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    pdf.cell(90, 6, "Defense/ITAR Security Lead: ___________________", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(90, 6, "Signature: ___________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(str(target_file))
    return str(target_file.resolve())
