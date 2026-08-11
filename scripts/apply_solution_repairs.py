"""Apply reviewed repairs from a `repair_authored_solutions.py` dump to the bank YAML (D-266).

    uv run --package intellichoice-curriculum python scripts/apply_solution_repairs.py \
      --dump out.json [--write]

**Dry by default.** Without `--write` it prints exactly what would change and touches nothing.

**Only items that were accepted *and* whose last step states the answer** are applied - the
strict D-265 test, not the lenient one that reported three unfixed items as successes.

**This writes YAML, which is not the end of the workflow.** The bank file must match what
`make question-export` produces, byte for byte and in order, or the next export shows a
spurious diff. The round trip that guarantees it:

    apply -> make curriculum-load   (re-gates every edited item through §5.8.5, D-235)
          -> make question-export   (rewrites the file from the database's approved set)

Editing and exporting are different operations and only the second defines the file's canonical
form. Running the load also means a repair that breaks the deterministic gate is refused here
rather than discovered on a deploy.
"""

import argparse
import json
import pathlib
import sys

import yaml

_BANK = pathlib.Path(__file__).resolve().parents[1] / "curriculum" / "internal_math" / "authored"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit_solution_step_completeness import classify, last_step_text  # noqa: E402
from intellichoice_curriculum.hint_solution_repair import (  # noqa: E402
    carry_misconception_notes,
)
from intellichoice_shared.bedrock import SolutionStep  # noqa: E402


def _states_answer(steps: list[dict], final: str) -> bool:
    return classify(last_step_text(steps[-1]), str(final)) is None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", required=True)
    parser.add_argument("--write", action="store_true", help="actually edit the bank files")
    args = parser.parse_args()

    records = json.load(open(args.dump))["records"]
    usable = {}
    for record in records:
        if record["outcome"]["status"] != "accepted":
            continue
        usable[record["question_template_id"]] = record

    applied, skipped, missing = [], [], []
    for path in sorted(_BANK.glob("*.yaml")):
        parsed = yaml.safe_load(path.read_text())
        changed = False
        for template in parsed["templates"]:
            record = usable.get(template["question_template_id"])
            if record is None:
                continue
            # D-267: the dump predates the corrected bound, so two of its accepted repairs
            # carry four-rung ladders that `AuthoredGeneratedItemResponse` forbids. Refusing
            # them here rather than letting the loader do it keeps the failure legible - the
            # loader reports a Pydantic error against a whole file, this names the item.
            if len(record["after_hint_ladder"]) != len(template["hint_ladder"]):
                skipped.append(
                    (
                        template["question_template_id"],
                        f"ladder went {len(template['hint_ladder'])} -> "
                        f"{len(record['after_hint_ladder'])} rungs",
                    )
                )
                continue
            final = template["canonical_solution"]["final_answer"]
            if not _states_answer(record["after_solution_steps"], final):
                # D-265: accepted is not the same as fixed. Three items reached acceptance
                # with the answer still unstated, and the lenient check called them clear.
                skipped.append((template["question_template_id"], "last step states no answer"))
                continue
            # D-269: dumps produced before the carry-over existed have every
            # `common_mistake` stripped - measured at 0 of 52 kept. Restoring here rather
            # than reimplementing the rule (D-223: one rule, one implementation).
            template["hint_ladder"] = record["after_hint_ladder"]
            before = [
                SolutionStep.model_validate(x)
                for x in template["canonical_solution"]["steps"]
            ]
            after = [
                SolutionStep.model_validate(x) for x in record["after_solution_steps"]
            ]
            template["canonical_solution"]["steps"] = [
                step.model_dump() for step in carry_misconception_notes(before, after)
            ]
            applied.append(template["question_template_id"])
            changed = True
        if changed and args.write:
            path.write_text(yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True))

    seen = {t for p in _BANK.glob("*.yaml") for t in
            [x["question_template_id"] for x in yaml.safe_load(p.read_text())["templates"]]}
    missing = [tid for tid in usable if tid not in seen]

    print(f"accepted in dump          : {len(usable)}")
    print(f"applied                   : {len(applied)}")
    print(f"skipped (still defective) : {len(skipped)}")
    for tid, why in skipped:
        print(f"    {tid:<44} {why}")
    if missing:
        print(f"in dump but not in bank   : {missing}")
    if not args.write:
        print("\n--dry: nothing written. Re-run with --write, then:")
        print("  make curriculum-load && make question-export")
        return 0
    print("\nWritten. The file is NOT canonical until:")
    print("  make curriculum-load && make question-export")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
