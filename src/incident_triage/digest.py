"""P6 — format the daily digest and send it over SMTP."""

from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText

from .aggregate import JobDigest


def format_digest_text(job_digests: list[JobDigest]) -> str:
    if not job_digests:
        return "No job failures in today's window. Nothing to triage."

    lines = [f"Incident digest — {len(job_digests)} job(s) with failures\n"]
    for jd in job_digests:
        lines.append(f"## {jd.job_name} (job_id={jd.job_id})")
        for r in jd.results:
            tag = "RECURRENT" if r.occurrences > 1 else "NEW"
            lines.append(
                f"  [{r.severity.value.upper()}] [{tag}] {r.task_key or '-'}\n"
                f"    root cause: {r.root_cause}\n"
                f"    action: {r.recommended_action.value} "
                f"(confidence {r.confidence:.2f}, transient_vs_real={r.transient_vs_real}, "
                f"occurrences={r.occurrences})"
            )
        lines.append("")
    return "\n".join(lines)


def send_digest_email(body: str, subject: str = "Incident Triage Copilot — daily digest") -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    to_addr = os.environ["DIGEST_TO_EMAIL"]

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
