import re
from typing import Any, TypedDict


class QuickReplyButton(TypedDict):
    type: str
    text: str


class TemplateButtons(TypedDict):
    buttons: list[QuickReplyButton]


class TemplateBody(TypedDict):
    text: str


class TemplateContent(TypedDict, total=False):
    body: TemplateBody
    buttons: TemplateButtons


class TemplateMapping(TypedDict, total=False):
    name: str
    type: str
    content: TemplateContent
    route: str
    status: str
    waba_id: str
    quality: str
    created_at: str


TEMPLATE_MAPPINGS: dict[str, TemplateMapping] = {
    "duplicate_candidate_agrees_gf9kqftzvwi62zvw": {
        "name": "duplicate_candidate_agrees",
        "type": "text",
        "content": {
            "body": {
                "text": "Great, thanks {{1}}!\r\nJust a few quick questions to see if this opportunity could be a good match for you.\r\nLet's start with your notice period. How about sharing below information?"
            },
            "buttons": {
                "buttons": [
                    {"type": "QUICK_REPLY", "text": "Immediate Joiner"},
                    {"type": "QUICK_REPLY", "text": "Less than 15 days"},
                    {"type": "QUICK_REPLY", "text": "Within a month"},
                    {"type": "QUICK_REPLY", "text": "More than a month"},
                ]
            },
        },
        "route": "promotional",
        "status": "APPROVED",
        "waba_id": "1007707438414877",
        "quality": "high",
        "created_at": "2026-06-19 22:03:20.243000",
    },
    "duplicate_notice_period_mcq_se6thv81qivs3rt2": {
        "name": "can_relocate",
        "type": "text",
        "content": {
            "body": {"text": "Are you willing to relocate (if required)?"},
            "buttons": {
                "buttons": [
                    {"type": "QUICK_REPLY", "text": "Of course"},
                    {"type": "QUICK_REPLY", "text": "May be not"},
                ]
            },
        },
        "route": "transactional",
        "status": "APPROVED",
        "waba_id": "1007707438414877",
        "quality": "high",
        "created_at": "2026-06-19 21:22:06.254000",
    },
    "duplicate_if_candidate_selects_not_interested_ddqhlau8q9d3q54l": {
        "name": "duplicate_if_candidate_selects_\"not_interested\"",
        "type": "text",
        "content": {
            "body": {
                "text": "No problem, {{1}}.\r\nThank you for your response. We'll make a note of your preference and won't bother you regarding this opportunity.\r\nWishing you all the very best in your career journey."
            }
        },
        "route": "promotional",
        "status": "APPROVED",
        "waba_id": "1007707438414877",
        "quality": "UNKNOWN",
        "created_at": "2026-06-18 18:07:42.234000",
    },
    "final_thankyou_message_2yzoyjaoczl5p2i0": {
        "name": "final_thank-you_message",
        "type": "text",
        "content": {
            "body": {
                "text": "Thank you for sharing the details, {{1}}.\r\nOur team will review your profile along with your responses and get back to you if there is a potential fit.\r\nWe appreciate your time and interest. Have a great day!"
            }
        },
        "route": "transactional",
        "status": "APPROVED",
        "waba_id": "1007707438414877",
        "quality": "high",
        "created_at": "2026-06-18 17:21:33.762000",
    },
    "expected_ctc_58xkmskwwotjakna": {
        "name": "expected_ctc",
        "type": "text",
        "content": {
            "body": {"text": "What would be your expected CTC for your next move?\r\nExample: ₹24 LPA"}
        },
        "route": "promotional",
        "status": "APPROVED",
        "waba_id": "1007707438414877",
        "quality": "high",
        "created_at": "2026-06-18 17:09:35.505000",
    },
    "current_ctc_e9a89qk8qptpa58q": {
        "name": "current_ctc",
        "type": "text",
        "content": {
            "body": {"text": "What is your current CTC?\r\n(Approximate figure is perfectly fine.)\r\nExample: ₹18 LPA"}
        },
        "route": "transactional",
        "status": "APPROVED",
        "waba_id": "1007707438414877",
        "quality": "high",
        "created_at": "2026-06-18 17:07:49.414000",
    },
    "initial_outreach1_3eecxy9dblhatrhm": {
        "name": "initial_outreach1",
        "type": "text",
        "content": {
            "body": {
                "text": "Hi {{1}},\r\nThis is {{2}} from {{3}}.\r\nI came across your profile and we currently have a {{4}} opportunity with {{5}} based in {{6}}.\r\nYour background looked relevant, so I wanted to reach out.\r\nWould it be okay if I shared a few details about the role?"
            },
            "buttons": {
                "buttons": [
                    {"type": "QUICK_REPLY", "text": "Yes, sure"},
                    {"type": "QUICK_REPLY", "text": "Tell me more"},
                    {"type": "QUICK_REPLY", "text": "Not interested"},
                ]
            },
        },
        "route": "promotional",
        "status": "APPROVED",
        "waba_id": "1007707438414877",
        "quality": "UNKNOWN",
        "created_at": "2026-06-18 17:03:08.197000",
    },
}

_PLACEHOLDER_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*|\d+)\s*}}")


def render_template(template_id: Any, sample: Any) -> str | None:
    mapping = TEMPLATE_MAPPINGS.get(str(template_id or ""))
    if mapping is None:
        return None

    content = mapping.get("content") or {}
    body = content.get("body") or {}
    text = str(body.get("text") or "")
    if not text:
        return None

    replacements = _template_replacements(text, sample)
    rendered = _PLACEHOLDER_PATTERN.sub(lambda match: replacements.get(match.group(1), match.group(0)), text)
    rendered = rendered.replace("\r\n", "\n")

    buttons = (content.get("buttons") or {}).get("buttons") or []
    button_texts = [str(button.get("text")) for button in buttons if isinstance(button, dict) and button.get("text")]
    if button_texts:
        rendered = f"{rendered} [Options: {' | '.join(button_texts)}]"
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
