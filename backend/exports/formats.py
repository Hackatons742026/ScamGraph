"""Render the masked campaign projection as standalone files."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import html
import io
import uuid


def render_csv(data: dict) -> bytes:
    output = io.StringIO(newline="")
    columns = ("record_type", "campaign_ref", "incident_ref", "peer_ref", "artifact_ref",
               "artifact_kind", "evidence_type", "tier", "family", "masked_ref",
               "funnel_step", "level", "score", "comparable", "first_seen", "last_seen")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    def write_row(row: dict) -> None:
        safe = {key: _safe_csv_cell(value) for key, value in row.items()}
        writer.writerow(safe)

    artifacts = {row["ref"]: row for row in data["artifacts"]}
    for incident in data["incidents"]:
        write_row({"record_type": "incident", "campaign_ref": data["campaign_ref"],
            "incident_ref": incident["ref"], "first_seen": incident["first_seen"] or "",
            "last_seen": incident["last_seen"] or ""})
    for item in data["artifacts"]:
        write_row({"record_type": "artifact", "campaign_ref": data["campaign_ref"],
            "incident_ref": item["incident_ref"], "artifact_ref": item["ref"],
            "artifact_kind": item["kind"], "funnel_step": item["funnel_step"] or ""})
    for item in data["evidence"]:
        artifact = artifacts.get(item["artifact_ref"], {})
        write_row({"record_type": "evidence", "campaign_ref": data["campaign_ref"],
            "incident_ref": item["incident_ref"], "artifact_ref": item["artifact_ref"] or "",
            "artifact_kind": item["artifact_kind"] or artifact.get("kind", ""),
            "evidence_type": item["type"], "tier": item["tier"],
            "family": item["family"] or "", "masked_ref": item["masked_ref"],
            "funnel_step": item["funnel_step"] or ""})
    for edge in data["edges"]:
        write_row({"record_type": "edge", "campaign_ref": data["campaign_ref"],
            "incident_ref": edge["source_ref"], "peer_ref": edge["target_ref"],
            "level": edge["level"], "score": edge["score"], "comparable": edge["comparable"]})
    return output.getvalue().encode("utf-8")


def _safe_csv_cell(value: object) -> object:
    """Prefix formula-like strings so spreadsheet apps treat them as text."""
    if not isinstance(value, str):
        return value
    significant = value.lstrip(" \t\r\n\ufeff")
    if value.startswith(("\t", "\r", "\n")) or significant.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def render_html(data: dict) -> bytes:
    esc = lambda value: html.escape(str(value if value is not None else ""), quote=True)
    incident_rows = "".join(
        f"<tr><td>{esc(item['ref'])}</td><td>{esc(item['first_seen'])}</td><td>{esc(item['last_seen'])}</td></tr>"
        for item in data["incidents"]
    )
    artifact_rows = "".join(
        f"<tr><td>{esc(item['ref'])}</td><td>{esc(item['incident_ref'])}</td>"
        f"<td>{esc(item['kind'])}</td><td>{esc(item['role'])}</td>"
        f"<td>{esc(item['parse_status'])}</td><td>{esc(item['funnel_step'])}</td></tr>"
        for item in data["artifacts"]
    )
    evidence_rows = "".join(
        f"<tr><td>{esc(item['incident_ref'])}</td><td>{esc(item['artifact_ref'])}</td>"
        f"<td>{esc(item['type'])}</td><td>{esc(item['tier'])}</td><td>{esc(item['family'])}</td>"
        f"<td>{esc(item['masked_ref'])}</td><td>{esc(item['funnel_step'])}</td></tr>"
        for item in data["evidence"]
    )
    edge_rows = "".join(
        f"<tr><td>{esc(item['source_ref'])}</td><td>{esc(item['target_ref'])}</td>"
        f"<td>{esc(item['level'])}</td><td>{esc(item['score'])}</td><td>{esc(item['comparable'])}</td></tr>"
        for item in data["edges"]
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>ScamGraph evidence pack {esc(data['campaign_ref'])}</title>
<style>body{{font:16px system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#172033}}
table{{border-collapse:collapse;width:100%;margin:1rem 0 2rem}}th,td{{border:1px solid #ccd3df;padding:.45rem;text-align:left;overflow-wrap:anywhere}}
th{{background:#edf1f7}}h1,h2{{color:#243b64}}.note{{color:#596579}}</style></head><body>
<h1>ScamGraph campaign evidence pack</h1><p>Campaign reference: <code>{esc(data['campaign_ref'])}</code></p>
<p>Generated at {esc(data['generated_at'])}. Identifiers and evidence values are pseudonymous references.
Raw source values, filenames, OCR, hashes, and filesystem paths are excluded.</p>
<h2>Incidents</h2><table><thead><tr><th>Reference</th><th>First seen</th><th>Last seen</th></tr></thead><tbody>{incident_rows}</tbody></table>
<h2>Artifacts and provenance</h2><table><thead><tr><th>Artifact ref</th><th>Incident ref</th><th>Kind</th><th>Role</th><th>Parse status</th><th>Funnel step</th></tr></thead><tbody>{artifact_rows}</tbody></table>
<h2>Evidence</h2><table><thead><tr><th>Incident ref</th><th>Artifact ref</th><th>Type</th><th>Tier</th><th>Family</th><th>Masked reference</th><th>Funnel step</th></tr></thead><tbody>{evidence_rows}</tbody></table>
<h2>Campaign links</h2><table><thead><tr><th>Source</th><th>Target</th><th>Level</th><th>Score</th><th>Comparable types</th></tr></thead><tbody>{edge_rows}</tbody></table>
<p class="note">This export is investigative evidence, not a fraud verdict or identity attribution.</p></body></html>"""
    return document.encode("utf-8")


def render_misp(data: dict) -> bytes:
    import json

    generated = datetime.fromisoformat(data["generated_at"])
    timestamp = str(int(generated.astimezone(timezone.utc).timestamp()))
    event_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"scamgraph:{data['campaign_ref']}"))
    org_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "scamgraph:org"))
    attributes = []
    for index, item in enumerate(data["evidence"]):
        attr_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL,
            f"scamgraph:{data['campaign_ref']}:{item['incident_ref']}:{item['masked_ref']}:{index}"))
        attributes.append({
            "id": "0",
            "event_id": "0",
            "distribution": "0",
            "timestamp": timestamp,
            "uuid": attr_uuid,
            "type": "text",
            "category": "Other",
            "value": f"masked:{item['type']}:{item['masked_ref']}",
            "to_ids": False,
            "comment": (f"ScamGraph tier {item['tier']}; incident {item['incident_ref']}; "
                        f"artifact {item['artifact_ref'] or 'unknown'}; funnel step {item['funnel_step']}"),
        })
    event = {
        "id": "0",
        "org_id": "0",
        "orgc_id": "0",
        "uuid": event_uuid,
        "info": f"ScamGraph masked campaign {data['campaign_ref']}",
        "threat_level_id": "4",
        "analysis": "0",
        "timestamp": timestamp,
        "distribution": "0",
        "published": False,
        "Orgc": {"id": "0", "name": "ScamGraph", "uuid": org_uuid},
        "Attribute": attributes,
    }
    # MISP's event date is optional; omit it when no source timestamp exists.
    if data.get("date"):
        event["date"] = data["date"]
    payload = {"Event": event}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
