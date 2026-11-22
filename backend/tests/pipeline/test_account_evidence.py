"""Account identifiers (e-mail, bank accounts, phones) and kit signals; synthetic values only."""

from __future__ import annotations

import json
from pathlib import Path

from backend.pipeline.extract.extractors import (
    extract_har,
    extract_html,
    extract_text,
    extract_url,
    mask_identifiers,
)
from backend.pipeline.intake.har import parse_har
from backend.pipeline.intake.html import parse_html
from backend.pipeline.models import Artifact, ArtifactKind

SALT = "synthetic-account-salt"
# Canonical documentation IBANs (valid checksums, not real customer accounts).
IBAN_PL = "PL61109010140000071219812874"
IBAN_DE = "DE89370400440532013000"


def _text_art() -> Artifact:
    return Artifact(id="art-text", incident_id="inc", kind=ArtifactKind.TEXT, path="note.txt")


def _by_type(evidence, kind):
    return [e for e in evidence if e.type == kind]


def test_emails_are_tier_a_masked_and_never_telegram_handles() -> None:
    evidence = extract_text(_text_art(), "Wypłaty: Wyplaty.Vista@vista-mail.test, wzór: jan@example.com.", salt=SALT)
    emails = _by_type(evidence, "email")
    assert [(e.display, e.tier.value if hasattr(e.tier, "value") else e.tier) for e in emails] == [
        ("wy…@vista-mail.test", "A"), ("ja…@example.com", "A")]
    assert not emails[0].ignored
    assert emails[1].ignored and emails[1].ignore_reason == "placeholder_email"
    assert _by_type(evidence, "telegram") == []


def test_same_mailbox_matches_regardless_of_case() -> None:
    first = _by_type(extract_text(_text_art(), "Kontakt: Wyplaty.Vista@Vista-Mail.test", salt=SALT), "email")
    second = _by_type(extract_text(_text_art(), "kontakt wyplaty.vista@vista-mail.test", salt=SALT), "email")
    assert first[0].value_hash == second[0].value_hash


def test_mailto_links_are_emails(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text("<html><body><a href='mailto:pomoc@paczka-help.test?subject=x'>Napisz</a></body></html>")
    art = Artifact(id="art-page", incident_id="inc", kind="html", path=str(page))
    evidence = extract_html(art, parse_html(page, salt=SALT), salt=SALT)
    assert [e.display for e in _by_type(evidence, "email")] == ["po…@paczka-help.test"]


def test_bank_accounts_with_or_without_spaces_are_ibans_not_phones() -> None:
    spaced = "Wpłata na rachunek PL61 1090 1014 0000 0712 1981 2874 do jutra."
    compact = f"Przelew: {IBAN_DE}."
    nrb = "Numer konta: 61 1090 1014 0000 0712 1981 2874."
    results = {name: extract_text(_text_art(), text, salt=SALT) for name, text in
               (("spaced", spaced), ("compact", compact), ("nrb", nrb))}
    for name, evidence in results.items():
        assert len(_by_type(evidence, "iban")) == 1, name
        assert _by_type(evidence, "phone") == [], name
    assert results["spaced"][0].display == "PL61 **** 2874"
    # The spaced IBAN and the domestic NRB are the same account.
    assert _by_type(results["spaced"], "iban")[0].value_hash == _by_type(results["nrb"], "iban")[0].value_hash


def test_invalid_checksums_and_short_numbers_are_not_accounts_or_phones() -> None:
    evidence = extract_text(_text_art(), "Kod PL00 1234 0000 1111 2222 3333 4444, cena 1 000 000 zł, "
                                         "zadzwoń +48 512 345 678.", salt=SALT)
    assert _by_type(evidence, "iban") == []
    assert [e.display for e in _by_type(evidence, "phone")] == ["48…78"]


def test_sentence_displays_mask_accounts_emails_and_phones() -> None:
    text = (f"Dopłatę przelej na rachunek {IBAN_PL} albo napisz na pomoc@paczka-help.test lub zadzwoń "
            "pod numer +48 512 345 678 jeszcze dziś wieczorem.")
    sentences = [e.display for e in _by_type(extract_text(_text_art(), text, salt=SALT), "shared_sentence")]
    assert sentences and all(IBAN_PL not in s and "pomoc@" not in s and "512 345 678" not in s for s in sentences)
    assert mask_identifiers(text).count("PL61 **** 2874") == 1


def test_generic_tracking_parameters_do_not_form_a_kit_signature() -> None:
    url_art = Artifact(id="art-url", incident_id="inc", kind=ArtifactKind.URL, path="url.txt")
    assert _by_type(extract_url(url_art, "https://shop-synthetic.test/?utm_source=fb&fbclid=X", salt=SALT),
                    "url_param_set") == []
    kit = _by_type(extract_url(url_art, "https://go.synthetic.test/c?clickid=1&sub=2&utm_source=fb", salt=SALT),
                   "url_param_set")
    assert [e.display for e in kit] == ["clickid,sub"]


def _har(tmp_path: Path, name: str, script_name: str, script: str) -> Path:
    path = tmp_path / f"{name}.har"
    path.write_text(json.dumps({"log": {"entries": [
        {"request": {"method": "GET", "url": f"https://{name}.test/?utm_source=fb", "headers": []},
         "response": {"status": 200, "headers": [], "content": {"mimeType": "text/html", "text": "<html></html>"}}},
        {"request": {"method": "GET", "url": f"https://{name}.test/js/{script_name}", "headers": []},
         "response": {"status": 200, "headers": [],
                      "content": {"mimeType": "application/javascript", "text": script}}},
        {"request": {"method": "GET", "url": "https://www.facebook.com/tr?id=1&ev=PageView", "headers": []},
         "response": {"status": 200, "headers": [], "content": {"mimeType": "image/gif"}}},
    ]}}))
    return path


def test_har_scripts_are_compared_by_content_not_name(tmp_path: Path) -> None:
    def kit(name, script_name, script):
        path = _har(tmp_path, name, script_name, script)
        art = Artifact(id=f"art-{name}", incident_id="inc", kind="har", path=str(path))
        evidence = extract_har(art, parse_har(path, salt=SALT), salt=SALT)
        assert _by_type(evidence, "url_param_set") == []  # utm_source and platform params only
        return _by_type(evidence, "js_hash")[0]

    same_a = kit("operator-a-one", "main.js", "/* kit A */ start();")
    same_a_renamed = kit("operator-a-two", "bundle.min.js", "/* kit A */ start();")
    other = kit("operator-b", "main.js", "/* kit B */ go();")
    assert same_a.value_hash == same_a_renamed.value_hash
    assert same_a.value_hash != other.value_hash
    assert same_a.display == "js:main.js"
