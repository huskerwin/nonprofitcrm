"""AI-assisted heuristic scanner for potential HIPAA-sensitive content."""

from __future__ import annotations

import re
from typing import Any, Iterable


_SSN_PATTERN = re.compile(r"\b(?:\d{3}-\d{2}-\d{4}|\d{9})\b")
_DOB_PATTERN = re.compile(
    r"\b(?:dob|date\s*of\s*birth|born)\b[^\n\r]{0,28}"
    r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
    re.IGNORECASE,
)
_MRN_PATTERN = re.compile(
    r"\b(?:mrn|medical\s*record(?:\s*number)?|patient\s*id)\b[^\n\r]{0,20}"
    r"[:#-]?\s*[A-Z0-9-]{5,}",
    re.IGNORECASE,
)
_INSURANCE_PATTERN = re.compile(
    r"\b(?:member\s*id|policy\s*(?:id|number)|subscriber\s*id|group\s*number)\b[^\n\r]{0,20}"
    r"[:#-]?\s*[A-Z0-9-]{4,}",
    re.IGNORECASE,
)
_ICD_CPT_PATTERN = re.compile(
    r"\b(?:icd-?10|icd-?9|cpt)\b[^\n\r]{0,16}\b[A-Z]?\d{2,4}(?:\.\d{1,4})?\b",
    re.IGNORECASE,
)

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})")
_ADDRESS_PATTERN = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,4}\s+"
    r"(?:st|street|ave|avenue|rd|road|dr|drive|blvd|boulevard|lane|ln|way|ct|court)\b",
    re.IGNORECASE,
)

_MEDICAL_TERMS = {
    "admission",
    "addiction",
    "adhd",
    "afib",
    "aids",
    "aki",
    "allergies",
    "allergy",
    "alzheimer disease",
    "alzheimer's disease",
    "alzheimers disease",
    "amputation",
    "anemia",
    "aneurysm",
    "angina",
    "anxiety",
    "arrhythmia",
    "arthritis",
    "asthma",
    "atrial fibrillation",
    "autism",
    "autoimmune",
    "bipolar",
    "bipolar disorder",
    "biopsy",
    "blood clot",
    "blood glucose",
    "blood pressure",
    "blood test",
    "born",
    "brain injury",
    "bronchitis",
    "burn",
    "cad",
    "cancer",
    "cardiac",
    "cardiology",
    "cardiomyopathy",
    "care plan",
    "cat scan",
    "catheter",
    "cbc",
    "cerebral palsy",
    "cervical spine",
    "cesarean",
    "c-section",
    "chemotherapy",
    "chf",
    "chronic kidney disease",
    "chronic pain",
    "chronic",
    "cirrhosis",
    "clinical",
    "clinician",
    "cognition",
    "cognitive impairment",
    "colitis",
    "comorbidity",
    "concussion",
    "condition",
    "congenital",
    "congestive heart failure",
    "copd",
    "coronary artery disease",
    "covid 19",
    "covid-19",
    "crohn disease",
    "crohn's disease",
    "crohns disease",
    "ct scan",
    "cva",
    "deep vein thrombosis",
    "defibrillator",
    "dementia",
    "depression",
    "dermatology",
    "diabetes",
    "diabetes mellitus",
    "diagnosed",
    "diagnosis",
    "diagnostic",
    "dialysis",
    "disability",
    "discharge",
    "disease",
    "dob",
    "doctor",
    "dose",
    "dosage",
    "drug interaction",
    "dvt",
    "ecg",
    "echo",
    "echocardiogram",
    "eczema",
    "eeg",
    "ekg",
    "embolism",
    "emergency department",
    "emergency room",
    "emphysema",
    "endocrinology",
    "epilepsy",
    "er",
    "fetal",
    "fibromyalgia",
    "follow-up",
    "follow up",
    "fracture",
    "gastroenterology",
    "gastroenteritis",
    "gerd",
    "glucose",
    "gyn",
    "gynecology",
    "head injury",
    "heart attack",
    "heart failure",
    "heart rate",
    "hematology",
    "hemorrhage",
    "hepatitis",
    "hiv",
    "hormone",
    "hospital",
    "htn",
    "hypertension",
    "hyperglycemia",
    "hyperlipidemia",
    "hyperthyroidism",
    "hypoglycemia",
    "hypotension",
    "hypothyroidism",
    "ibd",
    "ibs",
    "icd",
    "imaging",
    "immunology",
    "immunotherapy",
    "infection",
    "infectious disease",
    "infertility",
    "influenza",
    "infusion",
    "inpatient",
    "insomnia",
    "insulin",
    "intensive care",
    "intubation",
    "injury",
    "inpatient",
    "kidney disease",
    "kidney failure",
    "lab result",
    "labor and delivery",
    "laceration",
    "leukemia",
    "liver disease",
    "liver failure",
    "lupus",
    "lymphoma",
    "malignancy",
    "mammogram",
    "medication",
    "medications",
    "mental health",
    "metastasis",
    "metastatic",
    "mi",
    "migraine",
    "mobility",
    "motor deficit",
    "mrsa",
    "ms",
    "multiple sclerosis",
    "musculoskeletal",
    "myocardial infarction",
    "neonatal",
    "neoplasm",
    "nephrology",
    "neurologic",
    "neurology",
    "neuropathy",
    "nicu",
    "nurse",
    "obesity",
    "obs",
    "obstetrics",
    "ocd",
    "oncology",
    "operation",
    "opioid",
    "opioid use disorder",
    "orthopedic",
    "orthopedics",
    "osteoarthritis",
    "osteoporosis",
    "ot",
    "outpatient",
    "oxygen saturation",
    "pacemaker",
    "pain management",
    "pain",
    "panic disorder",
    "paralysis",
    "paraplegia",
    "pathology",
    "patient",
    "pediatrics",
    "pediatric",
    "pe",
    "physical therapy",
    "physician",
    "pneumonia",
    "post op",
    "post-op",
    "postpartum",
    "prenatal",
    "prescription",
    "prescriptions",
    "primary care",
    "procedure",
    "prognosis",
    "provider",
    "psychiatric",
    "psychiatry",
    "psychology",
    "pt",
    "ptsd",
    "pulmonary",
    "pulmonary embolism",
    "quadriplegia",
    "radiation therapy",
    "radiology",
    "radiotherapy",
    "rehab",
    "rehabilitation",
    "renal failure",
    "respiratory failure",
    "respiratory therapy",
    "rheumatoid arthritis",
    "sars-cov-2",
    "schizophrenia",
    "sci",
    "seizure",
    "sepsis",
    "sleep apnea",
    "spasticity",
    "specialist",
    "speech therapy",
    "spinal",
    "spinal cord",
    "spinal cord injury",
    "spo2",
    "sprain",
    "sti",
    "std",
    "stroke",
    "substance use disorder",
    "suicidal ideation",
    "surgery",
    "symptom",
    "symptoms",
    "tachycardia",
    "tb",
    "tbi",
    "therapy",
    "thrombosis",
    "thyroid",
    "transplant",
    "trauma",
    "traumatic brain injury",
    "treatment",
    "treatment plan",
    "triage",
    "tumor",
    "tuberculosis",
    "ulcer",
    "ulcerative colitis",
    "ultrasound",
    "urgent care",
    "urology",
    "urinary tract infection",
    "uti",
    "ventilator",
    "viral load",
    "vital signs",
    "wound",
    "x-ray",
}

_MEDICAL_TERM_PATTERNS = [
    (term, re.compile(rf"\b{re.escape(term)}\b"))
    for term in sorted(_MEDICAL_TERMS, key=len, reverse=True)
]

_HIGH_RISK_NOTES_FIELDS = {
    "notes",
    "summary",
    "description",
    "next_step",
}


def _severity_rank(severity: str) -> int:
    return {"High": 3, "Medium": 2, "Low": 1}.get(severity, 0)


def _mask_match_text(text: str) -> str:
    clean = " ".join(text.split())
    if len(clean) <= 6:
        return "***"
    return f"{clean[:2]}...{clean[-2:]}"


def _excerpt(text: str, start: int, end: int, window: int = 34) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    snippet = " ".join(text[left:right].split())
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet = snippet + "..."
    return snippet


def _contains_medical_context(text_lower: str) -> list[str]:
    return [term for term, pattern in _MEDICAL_TERM_PATTERNS if pattern.search(text_lower)]


def _identifier_hits(text: str) -> list[str]:
    hits: list[str] = []
    if _EMAIL_PATTERN.search(text):
        hits.append("email")
    if _PHONE_PATTERN.search(text):
        hits.append("phone")
    if _ADDRESS_PATTERN.search(text):
        hits.append("address")
    return hits


class HipaaSensitivityScanner:
    """Scan records and return potential HIPAA-sensitive findings."""

    def scan_records(self, records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for record in records:
            object_name = str(record.get("object_name") or "Unknown")
            table_name = str(record.get("table_name") or "unknown")
            record_id_raw = record.get("record_id")
            if not isinstance(record_id_raw, int):
                continue

            fields = record.get("fields")
            if not isinstance(fields, dict):
                continue

            for field_name, raw_value in fields.items():
                if not isinstance(raw_value, str):
                    continue

                text = raw_value.strip()
                if not text:
                    continue

                findings.extend(
                    self._scan_field(
                        object_name=object_name,
                        table_name=table_name,
                        record_id=record_id_raw,
                        field_name=str(field_name),
                        text=text,
                    )
                )

        findings.sort(
            key=lambda row: (
                _severity_rank(str(row["severity"])),
                int(row["confidence"]),
                str(row["object_name"]),
                int(row["record_id"]),
            ),
            reverse=True,
        )
        return findings

    def _scan_field(
        self,
        object_name: str,
        table_name: str,
        record_id: int,
        field_name: str,
        text: str,
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        dedupe: set[tuple[str, str]] = set()

        def add_finding(
            signal: str,
            severity: str,
            confidence: int,
            reason: str,
            matched_text: str,
            start: int,
            end: int,
        ) -> None:
            dedupe_key = (signal, matched_text.lower())
            if dedupe_key in dedupe:
                return
            dedupe.add(dedupe_key)

            findings.append(
                {
                    "object_name": object_name,
                    "table_name": table_name,
                    "record_id": record_id,
                    "field_name": field_name,
                    "signal": signal,
                    "severity": severity,
                    "confidence": confidence,
                    "matched_text": _mask_match_text(matched_text),
                    "context": _excerpt(text, start, end),
                    "reason": reason,
                }
            )

        for match in _SSN_PATTERN.finditer(text):
            add_finding(
                signal="SSN",
                severity="High",
                confidence=99,
                reason="Matches US Social Security Number pattern.",
                matched_text=match.group(0),
                start=match.start(),
                end=match.end(),
            )

        for match in _MRN_PATTERN.finditer(text):
            add_finding(
                signal="Medical Record Number",
                severity="High",
                confidence=94,
                reason="Contains MRN or patient ID marker.",
                matched_text=match.group(0),
                start=match.start(),
                end=match.end(),
            )

        for match in _DOB_PATTERN.finditer(text):
            add_finding(
                signal="Date of Birth",
                severity="High",
                confidence=92,
                reason="Contains DOB/date-of-birth context.",
                matched_text=match.group(0),
                start=match.start(),
                end=match.end(),
            )

        for match in _INSURANCE_PATTERN.finditer(text):
            add_finding(
                signal="Insurance Identifier",
                severity="High",
                confidence=90,
                reason="Contains insurance member or policy identifier.",
                matched_text=match.group(0),
                start=match.start(),
                end=match.end(),
            )

        for match in _ICD_CPT_PATTERN.finditer(text):
            add_finding(
                signal="Clinical Billing Code",
                severity="Medium",
                confidence=82,
                reason="Contains ICD/CPT clinical coding pattern.",
                matched_text=match.group(0),
                start=match.start(),
                end=match.end(),
            )

        text_lower = text.lower()
        medical_terms = _contains_medical_context(text_lower)
        identifiers = _identifier_hits(text)

        if medical_terms and identifiers:
            first_term = medical_terms[0]
            first_id = identifiers[0]
            start = max(text_lower.find(first_term), 0)
            end = min(start + len(first_term), len(text))
            add_finding(
                signal="Medical Context + Identifier",
                severity="High",
                confidence=89,
                reason=(
                    f"Contains medical context ('{first_term}') with personal identifier ({first_id})."
                ),
                matched_text=first_term,
                start=start,
                end=end,
            )
        elif medical_terms and field_name.lower() in _HIGH_RISK_NOTES_FIELDS:
            first_term = medical_terms[0]
            start = max(text_lower.find(first_term), 0)
            end = min(start + len(first_term), len(text))
            add_finding(
                signal="Medical Context",
                severity="Medium",
                confidence=74,
                reason=f"Unstructured field contains medical term '{first_term}'.",
                matched_text=first_term,
                start=start,
                end=end,
            )

        return findings
