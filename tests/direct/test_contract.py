"""Direct behavior and edge tests for this contract."""

import json
import pytest

def address(value):
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    return str(value)

def mock(direct_vm, result, pattern=r".*"):
    direct_vm.clear_mocks()
    direct_vm.mock_llm(pattern, json.dumps(result))

def _address(value):
    return "0x" + bytes(value).hex() if isinstance(value, (bytes, bytearray)) else str(value)

def _mock(vm, answer):
    vm.clear_mocks()
    vm.mock_llm(r".*", json.dumps(answer))

def test_split_slip_item_ledger_and_exact_total(deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    contract = deploy("split_slip.py")
    diners = json.dumps([address(direct_bob), address(direct_charlie)])
    mock(direct_vm, {"items": [
        {"name": "Soup", "cents": 900}, {"name": "Pasta", "cents": 1500}],
        "tax_cents": 101, "tip_cents": 100, "total_cents": 2601})
    receipt_id = contract.capture("lunch", diners, b"demo-receipt-image")
    with direct_vm.expect_revert("unassigned_or_finalized"):
        contract.finalize(receipt_id)
    contract.assign_item(receipt_id, 0, address(direct_bob))
    contract.assign_item(receipt_id, 1, address(direct_charlie))
    contract.finalize(receipt_id)
    shares = contract.get_receipt(receipt_id)["shares_cents"]
    assert sum(shares.values()) == 2601
    assert sorted(shares.values()) == [1001, 1600]
    with direct_vm.expect_revert("already_finalized"):
        contract.assign_item(receipt_id, 0, address(direct_bob))
    mock(direct_vm, {"items": [{"name": "Soup", "cents": 900}],
                     "tax_cents": 100, "tip_cents": 0, "total_cents": 950})
    with direct_vm.expect_revert("receipt_total_mismatch"):
        contract.capture("bad-total", diners, b"demo-receipt-image")

def test_split_slip_owner_only_assignment(deploy, direct_vm, direct_bob, direct_charlie):
    contract = deploy("split_slip.py")
    _mock(direct_vm, {"items": [{"name": "Soup", "cents": 900}],
                      "tax_cents": 0, "tip_cents": 0, "total_cents": 900})
    receipt_id = contract.capture("meal", json.dumps([_address(direct_bob), _address(direct_charlie)]), b"image")
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only_owner"):
        contract.assign_item(receipt_id, 0, _address(direct_bob))
