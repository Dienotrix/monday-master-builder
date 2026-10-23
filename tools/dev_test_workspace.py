"""Development only (A31): make the test workspace the user named a build target of one strand of a client record.

`ledger.py workspaces` accepts only a workspace the build created (A21), so a demo built inside the named test
workspace has no way to target it (demo 1, finding 8). This tool writes the three `guard_index` fields `ledger.py
intent` reads, under the record mutex, and prints what it changed. It never ships: it lives in tools/, beside the
release lint. Run it after `ledger.py bind` and before `ledger.py run start`.

    python3 tools/dev_test_workspace.py --record <client folder> --strand 001 --workspace <id> [--product core]

Without `--product`, a workspace the record already knows keeps its product, and a new one is `core`; a product that
differs from the one the record holds is refused (demo 4, build note 4: the CRM test workspace was nearly relabelled).
"""
import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "monday-master-builder" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import mmb_common as mc  # noqa: E402


def target(record, strand, workspace, product):
    """Add `workspace` to the strand's build targets; returns the fields as written."""
    if not re.fullmatch(r"[1-9][0-9]*", workspace):
        raise SystemExit("--workspace: digits with no leading zero, the id monday gives")
    if not re.fullmatch(r"\d{3}", strand):
        raise SystemExit("--strand: the three-digit short id, such as 001")
    if product not in (None, "core", "crm", "service"):
        raise SystemExit("--product: core, crm or service")
    path = record / "account.json"
    with mc.record_mutex(record):
        account = mc.read_json(path, "account.json")
        if str((account.get("account") or {}).get("id")) in ("None", "unbound"):
            raise SystemExit("account.json is not bound yet: run ledger.py bind first")
        index = account.setdefault("guard_index", {})
        kinds = index.get("product_workspaces") or {}
        have = kinds.get(workspace)
        if product is None:
            product = have or "core"
        elif have and have != product:
            raise SystemExit("--product: the record holds this workspace as %s, and a workspace keeps its product" % have)
        ids = index.setdefault("client_workspace_ids", [])
        if workspace not in ids:
            ids.append(workspace)
        entry = index.setdefault("build_targets_by_strand", {}).setdefault(strand, {})
        entry.setdefault("workspace_ids", [])
        entry.setdefault("folder_ids", [])
        if workspace not in entry["workspace_ids"]:
            entry["workspace_ids"].append(workspace)
        kinds[workspace] = product
        index["product_workspaces"] = kinds
        mc.write_file(path, mc.json_text(account), record)
    return {"client_workspace_ids": ids, "build_targets": entry, "product": product}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", required=True)
    parser.add_argument("--strand", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--product", default=None)
    args = parser.parse_args(argv)
    result = target(Path(args.record).resolve(), args.strand, args.workspace, args.product)
    print(json.dumps({"ok": True, "written": "account.json", **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
