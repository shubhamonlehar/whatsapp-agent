import re
from typing import Any


TemplateMapping = dict[str, Any]


INTERVIEW_REMINDER_NEW: TemplateMapping = {
    "name": "interview_reminder_new",
    "type": "text",
    "content": {
        "body": {
            "text": "Hi {{1}}, a quick reminder - your interview for {{2}} at {{3}} starts in 30 minutes."
        }
    },
}


TEMPLATE_MAPPINGS: dict[str, TemplateMapping] = {
    "candidate_missed_dngfcr2aguu2nnh2": {
        "name": "candidate_missed",
        "type": "text",
        "content": {
            "body": {
                "text": "Hi {{1}}, this is {{2}} from {{3}}. We just tried calling you about your application."
            }
        },
    },
    "candidate_cv_reqquest_18bva1mbdlo8c907": {
        "name": "candidate_cv_request",
        "label": "Candidate CV Request Template",
        "type": "text",
        "content": {
            "body": {
                "text": "Hi {{1}}, thanks for your interest in the {{2}} role at {{3}}."
            }
        },
    },
    "interview_confirmation_cxrn27hlbuhveryj": {
        "name": "interview_confirmation",
        "type": "text",
        "content": {
            "body": {
                "text": "Interview Confirmation: Hi {{1}}, your interview for {{2}} at {{3}} is confirmed on {{4}}."
            }
        },
    },
    "duplicate_interview_reminder_yeaygobldbv2m1z": INTERVIEW_REMINDER_NEW,
    "duplicate_interview_reminder_yeaygobldbvb2m1z": INTERVIEW_REMINDER_NEW,
    "interview_reminder_yeaygobldbv2m1z": {
        "name": "interview_reminder",
        "type": "text",
        "content": {
            "body": {
                "text": "Hi {{name}}, a quick reminder - your interview for {{role}} at {{company}} starts in 30 minutes."
            }
        },
    },
    "candidate_interview_confirmation_pada83q0zjxxvko0": {
        "name": "candidate_interview_confirmation",
        "type": "text",
        "content": {
            "body": {
                "text": "Hi {{name}}, your interview for {{role}} at {{company}} is confirmed on {{date}} at {{time}}."
            }
        },
    },
}

_PLACEHOLDER_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*|\d+)\s*}}")


def render_template(template_id: Any, sample: Any) -> str | None:
    mapping = TEMPLATE_MAPPINGS.get(str(template_id or ""))
    if mapping is None:
        return None

    text = str(mapping.get("content", {}).get("body", {}).get("text") or "")
    if not text:
        return None

    replacements = _template_replacements(text, sample)
    rendered = _PLACEHOLDER_PATTERN.sub(lambda match: replacements.get(match.group(1), match.group(0)), text)

    label = str(mapping.get("label") or "").strip()
    if label:
        return f"{label} : {rendered}"
    return rendered


def _template_replacements(text: str, sample: Any) -> dict[str, str]:
    if not isinstance(sample, dict):
        return {}

    replacements = {
        str(key): str(value)
        for key, value in sample.items()
        if key != "bodyvar" and not isinstance(value, (dict, list, tuple, set))
    }
    body_vars = sample.get("bodyvar")
    if not isinstance(body_vars, list):
        return replacements

    values = [str(value) for value in body_vars]
    for index, value in enumerate(values, start=1):
        replacements.setdefault(str(index), value)

    named_placeholders = [
        placeholder for placeholder in _PLACEHOLDER_PATTERN.findall(text) if not placeholder.isdigit()
    ]
    for placeholder, value in zip(dict.fromkeys(named_placeholders), values):
        replacements.setdefault(placeholder, value)
    return replacements
