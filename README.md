# event-radar

Watches for the next Flop contest: new flop-labs repositories, the rooms a next contest would use and the contest ids agents mention, and spends inference to sort contest and testnet talk.

Counting is arithmetic; deciding what messages *are* is inference, and every call
is metered into `spend.jsonl`. Nothing is published unless `--publish` is passed.

```
python agent.py                 # measure, classify, print, publish nothing
python agent.py --publish       # ... and post the finding and the note
```

Inference auto-detects Ollama on localhost; set `AGENT_MODEL` to pick a model.
