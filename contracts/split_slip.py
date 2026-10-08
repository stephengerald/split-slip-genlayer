# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""Consensus receipt transcription followed by a deterministic shared tab."""

from genlayer import *
import hashlib
import json


def _fail(code: str) -> None:
    raise gl.vm.UserError("[EXPECTED] " + code)


def _bad(code: str) -> None:
    raise gl.vm.UserError("[LLM_ERROR] " + code)


class SplitSlip(gl.Contract):
    receipts: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def capture(self, key: str, diners_json: str, image_data: bytes) -> str:
        clean_key = key.strip().lower()
        if not 1 <= len(clean_key) <= 40 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in clean_key):
            _fail("invalid_key")
        receipt_id = str(gl.message.sender_address).lower() + ":" + clean_key
        if self.receipts.get(receipt_id, ""):
            _fail("receipt_exists")
        try:
            diners = json.loads(diners_json)
        except (TypeError, ValueError):
            _fail("invalid_diners_json")
        if not isinstance(diners, list) or not 2 <= len(diners) <= 8:
            _fail("diner_count")
        clean_diners = []
        for diner in diners:
            if not isinstance(diner, str):
                _fail("invalid_diner")
            address = diner.lower()
            if len(address) != 42 or not address.startswith("0x") or any(c not in "0123456789abcdef" for c in address[2:]):
                _fail("invalid_diner")
            if address == "0x" + "0" * 40 or address in clean_diners:
                _fail("duplicate_or_zero_diner")
            clean_diners.append(address)
        if not 1 <= len(image_data) <= 150_000:
            _fail("image_size")
        prompt = (
            "Transcribe this clear restaurant receipt. Return JSON exactly "
            '{"items":[{"name":"...","cents":integer}],"tax_cents":integer,"tip_cents":integer,"total_cents":integer}. '
            "Use whole cents. Preserve each printed item as one row, do not invent charges, "
            "and use zero if tax or tip is absent. total_cents is the printed final total; "
            "if it is absent or inconsistent, return an invalid empty object."
        )

        def parse(value):
            if not isinstance(value, dict) or set(value) != {"items", "tax_cents", "tip_cents", "total_cents"}:
                _bad("receipt_shape")
            items = value["items"]
            if not isinstance(items, list) or not 1 <= len(items) <= 12:
                _bad("item_count")
            clean_items = []
            for item in items:
                if not isinstance(item, dict) or set(item) != {"name", "cents"}:
                    _bad("item_shape")
                name = item["name"]
                cents = item["cents"]
                if type(name) is not str or not 1 <= len(name.strip()) <= 60:
                    _bad("item_name")
                if type(cents) is not int or not 0 <= cents <= 1_000_000:
                    _bad("item_cents")
                clean_items.append({"name": name.strip(), "cents": cents})
            tax = value["tax_cents"]
            tip = value["tip_cents"]
            total = value["total_cents"]
            if type(tax) is not int or type(tip) is not int or not 0 <= tax <= 1_000_000 or not 0 <= tip <= 1_000_000:
                _bad("extras_cents")
            if type(total) is not int or total != sum(item["cents"] for item in clean_items) + tax + tip:
                _bad("receipt_total_mismatch")
            return {"items": clean_items, "tax_cents": tax, "tip_cents": tip, "total_cents": total}

        def leader_fn():
            return parse(gl.nondet.exec_prompt(prompt, images=[image_data], response_format="json"))

        def validator_fn(leader_result):
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                return parse(leader_result.calldata) == leader_fn()
            except Exception:
                return False

        data = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        self.receipts[receipt_id] = json.dumps(
            {"owner": str(gl.message.sender_address).lower(), "diners": clean_diners,
             "image_sha256": hashlib.sha256(image_data).hexdigest(),
             "items": data["items"], "tax_cents": data["tax_cents"], "tip_cents": data["tip_cents"],
             "total_cents": data["total_cents"],
             "assignments": [""] * len(data["items"]), "status": "ASSIGNING", "shares_cents": {}},
            sort_keys=True, separators=(",", ":"),
        )
        return receipt_id

    @gl.public.write
    def assign_item(self, receipt_id: str, item_index: u256, diner: str) -> None:
        raw = self.receipts.get(receipt_id, "")
        if not raw:
            _fail("receipt_missing")
        record = json.loads(raw)
        if record["owner"] != str(gl.message.sender_address).lower():
            _fail("only_owner")
        if record["status"] != "ASSIGNING":
            _fail("already_finalized")
        index = int(item_index)
        address = diner.lower()
        if index >= len(record["items"]) or address not in record["diners"]:
            _fail("invalid_assignment")
        record["assignments"][index] = address
        self.receipts[receipt_id] = json.dumps(record, sort_keys=True, separators=(",", ":"))

    @gl.public.write
    def finalize(self, receipt_id: str) -> None:
        raw = self.receipts.get(receipt_id, "")
        if not raw:
            _fail("receipt_missing")
        record = json.loads(raw)
        if record["owner"] != str(gl.message.sender_address).lower():
            _fail("only_owner")
        if record["status"] != "ASSIGNING" or any(not owner for owner in record["assignments"]):
            _fail("unassigned_or_finalized")
        shares = {diner: 0 for diner in record["diners"]}
        for index, owner in enumerate(record["assignments"]):
            shares[owner] += record["items"][index]["cents"]
        active = sorted(set(record["assignments"]))
        extra = record["tax_cents"] + record["tip_cents"]
        equal, remainder = divmod(extra, len(active))
        for index, diner in enumerate(active):
            shares[diner] += equal + (1 if index < remainder else 0)
        record["shares_cents"] = shares
        record["status"] = "FINALIZED"
        self.receipts[receipt_id] = json.dumps(record, sort_keys=True, separators=(",", ":"))

    @gl.public.view
    def get_receipt(self, receipt_id: str) -> dict:
        raw = self.receipts.get(receipt_id, "")
        if not raw:
            _fail("receipt_missing")
        return json.loads(raw)
