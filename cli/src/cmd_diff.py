"""`ctl diff <a> <b>` subcommand."""
from __future__ import annotations

import json
import sys

from .common import (
    EXIT_OK,
    EXIT_USER_ERROR,
    err,
    resource_of_id,
    load_resource_item,
)

HELP = """\
usage: ctl diff <a> <b>

Print a structured JSON diff between two resources identified by id.

The output shape is:
  {
    "only_in_a": { ... fields present only in A },
    "only_in_b": { ... fields present only in B },
    "changed":   { field: {"a": <a_value>, "b": <b_value>}, ... }
  }

Exit codes:
  0    success (including empty diff)
  1    neither id exists
"""


def _diff(a: dict, b: dict) -> dict:
    only_a: dict = {}
    only_b: dict = {}
    changed: dict = {}
    for k in a.keys() | b.keys():
        if k in a and k not in b:
            only_a[k] = a[k]
        elif k in b and k not in a:
            only_b[k] = b[k]
        else:
            if a[k] != b[k]:
                changed[k] = {"a": a[k], "b": b[k]}
    return {"only_in_a": only_a, "only_in_b": only_b, "changed": changed}


def run(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(HELP)
        return EXIT_OK

    if len(argv) < 2:
        err("diff requires two ids")
        return EXIT_USER_ERROR

    id_a, id_b = argv[0], argv[1]

    res_a = resource_of_id(id_a)
    res_b = resource_of_id(id_b)

    if res_a is None and res_b is None:
        err("not found")
        return EXIT_USER_ERROR

    # Gotcha: when the two ids belong to different resource types we silently
    # emit an empty diff instead of erroring. This is the documented
    # "diff u001 o001 -> {}" behaviour.
    if res_a != res_b:
        sys.stdout.write("{}\n")
        return EXIT_OK

    a = load_resource_item(res_a, id_a) or {}
    b = load_resource_item(res_b, id_b) or {}

    sys.stdout.write(json.dumps(_diff(a, b), indent=2, ensure_ascii=False) + "\n")
    return EXIT_OK
