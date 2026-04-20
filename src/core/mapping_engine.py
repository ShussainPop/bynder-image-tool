import re
from dataclasses import dataclass, field, replace


AMAZON_SLOTS = ("MAIN", "PT01", "PT02", "PT03", "PT04", "PT05", "PT06", "PT07", "PT08")


@dataclass(frozen=True)
class ParsedAsset:
    asset_id: str
    filename: str
    position_number: str | None
    position_label: str | None
    extension: str | None


@dataclass(frozen=True)
class ProductLineRules:
    regex: str
    label_to_slot: dict[str, str]


@dataclass
class SlotAssignmentResult:
    assigned: dict[str, ParsedAsset] = field(default_factory=dict)
    unmapped: list[ParsedAsset] = field(default_factory=list)


SlotAssignment = SlotAssignmentResult  # alias to match test import


_DEFAULT_REGEX = r"_(\d{2})_(\w+)\.(png|jpg|jpeg)$"


def infer_regex(sample_filenames: list[str]) -> str:
    pattern = re.compile(_DEFAULT_REGEX, re.IGNORECASE)
    if not all(pattern.search(s) for s in sample_filenames):
        raise ValueError(
            "Default regex does not match all samples. Edit the regex manually in the wizard."
        )
    return _DEFAULT_REGEX


def parse_filename(filename: str, regex: str) -> ParsedAsset | None:
    match = re.search(regex, filename, re.IGNORECASE)
    if not match:
        return None
    number, label, ext = match.group(1), match.group(2), match.group(3)
    return ParsedAsset(
        asset_id="",
        filename=filename,
        position_number=number,
        position_label=label,
        extension=ext.lower(),
    )


def assign_slots(
    assets: list[dict],
    rules: ProductLineRules,
) -> SlotAssignmentResult:
    """Assign parsed assets to Amazon slots.

    Collision policy: first asset (by input order) wins; later assets
    mapping to an already-filled slot go to `unmapped`. Callers that want
    deterministic collision resolution must pre-sort `assets`.
    """
    result = SlotAssignmentResult()
    for raw in assets:
        parsed_core = parse_filename(raw["filename"], rules.regex)
        if parsed_core is not None:
            parsed = replace(parsed_core, asset_id=raw["asset_id"])
        else:
            parsed = ParsedAsset(
                asset_id=raw["asset_id"],
                filename=raw["filename"],
                position_number=None,
                position_label=None,
                extension=None,
            )

        if parsed.position_label is None:
            result.unmapped.append(parsed)
            continue

        slot = rules.label_to_slot.get(parsed.position_label)
        if slot is None:
            result.unmapped.append(parsed)
            continue

        if slot in result.assigned:
            result.unmapped.append(parsed)
            continue

        result.assigned[slot] = parsed
    return result
