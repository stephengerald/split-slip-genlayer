# SplitSlip

Transcribes a bounded receipt image, reconciles the printed total, and lets an organizer assign line items for exact per-diner shares.

## Why this is an intelligent contract

A receipt-backed item-assignment ledger with a terminal share calculation; it never transfers funds. The source interpretation runs inside GenLayer consensus; the stored result and read methods are on-chain.

## Scope

The receipt image is public transaction input. OCR cannot prove the receipt is authentic; review the transcription before assigning items.

## Verify

```powershell
python -m pip install -r requirements.txt
genvm-lint check contracts/split_slip.py
genvm-lint typecheck contracts/split_slip.py
pytest tests/direct -q
gltest tests/integration/test_studionet.py --network studionet -v -s
```

Live tests submit permanent public StudioNet test transactions; use a fresh test wallet. See EVIDENCE.md for the completed run and explorer links.
