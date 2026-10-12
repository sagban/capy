#!/usr/bin/env python3
"""Fix Dependencies sections on backlog issues after seed script capture bug."""
import json
import subprocess
import sys

REPO = "sagban/capy"

DEPS = {
    13: "Parent epic #1 (E0)",
    14: "Blocked by #13; parent epic #1 (E0)",
    15: "Parent epic #1 (E0)",
    16: "Parent epic #1 (E0)",
    17: "Parent epic #1 (E0)",
    18: "Parent epic #1 (E0); related epic #5 (E4)",
    19: "Parent epic #1 (E0)",
    20: "Parent epic #1 (E0); blocks Phase 1 harness",
    21: "Parent epic #1 (E0)",
    22: "Parent epic #1 (E0)",
    23: "Parent epic #1 (E0); after epics exist",
    24: "Parent epic #1 (E0); blocks Phase 2 UI",
    25: "Parent epic #1 (E0)",
    26: "Parent epic #1 (E0); depends on #24 and #25",
    27: "Parent epic #1 (E0)",
    28: "Parent epic #1 (E0); feeds epic #4 (E3)",
    29: "Parent epic #3 (E2); Phase 0 data model docs (#19)",
    30: "Parent epic #3 (E2)",
    31: "Parent epic #3 (E2); depends on #29 and #30",
    32: "Parent epic #4 (E3); Phase 0 seed inventory (#28)",
    33: "Parent epic #4 (E3); Phase 0 secrets runbook (#14)",
    34: "Parent epic #5 (E4); Phase 0 harness docs (#18)",
    35: "Parent epic #5 (E4)",
    36: "Parent epic #5 (E4); epic #3 (E2)",
    37: "Parent epic #5 (E4)",
    38: "Parent epic #5 (E4)",
    39: "Parent epic #10 (E8)",
    40: "Parent epic #2 (E1); Phase 0 Firebase auth (#13)",
    41: "Parent epics #2 (E1) / #9 (E7b)",
    42: "Parent epics #6/#7/#8/#9; Phase 0 screen docs (#24)",
    43: "Parent epic #6 (E5)",
    44: "Parent epic #7 (E6)",
    45: "Parent epic #8 (E7)",
    46: "Parent epic #9 (E7b)",
    47: "Parent epics #7 (E6) / #8 (E7)",
    48: "Parent epics #5 (E4) / #6 (E5); Phase 1+2 complete",
    49: "Parent epic #3 (E2)",
    50: "Parent epics #6 (E5) / #7 (E6)",
    51: "Parent epics #3 (E2) / #6 (E5)",
    52: "Parent epic #10 (E8)",
    53: "Depends on Phase 3 integration issues #48–#52",
    54: "Parent epic #11 (E9)",
    55: "Parent epics #11 (E9) / #10 (E8)",
    56: "Parent epic #11 (E9)",
    57: "Parent epic #11 (E9)",
    58: "Parent epic #11 (E9)",
    59: "Parent epic #12 (E10)",
    60: "Parent epic #12 (E10)",
    61: "Parent epic #12 (E10); blocked by #59 (FR-9)",
    62: "Parent epic #12 (E10)",
    63: "Parent epics #12 (E10) / #10 (E8)",
}


def gh_json(*args):
    out = subprocess.check_output(["gh", *args, "--repo", REPO, "--json", "body"], text=True)
    return json.loads(out)["body"]


def gh_edit(num: int, body: str):
    subprocess.check_call(
        ["gh", "issue", "edit", str(num), "--repo", REPO, "--body", body],
        stdout=subprocess.DEVNULL,
    )


def main():
    for num, deps in sorted(DEPS.items()):
        body = gh_json("issue", "view", str(num))
        start = body.find("## Dependencies")
        end = body.find("## Out of scope")
        if start == -1 or end == -1:
            print(f"skip #{num}: missing sections", file=sys.stderr)
            continue
        new_body = body[:start] + "## Dependencies\n" + deps + "\n\n" + body[end:]
        gh_edit(num, new_body)
        print(f"fixed #{num}")


if __name__ == "__main__":
    main()
