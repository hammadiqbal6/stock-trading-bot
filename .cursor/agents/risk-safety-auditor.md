# Subagent: Risk / safety auditor

Checklist:

- [ ] LLM/advisory cannot call `submit_order` or mute risk limits
- [ ] Live trading double-gated in settings
- [ ] Kill switch, daily loss, max DD, position limits enforced before orders
- [ ] PDT awareness for accounts &lt; $25k when day-trading
- [ ] Paper default; no accidental live URL/credentials
- [ ] Secrets not logged

Fail the review if any hard rule is bypassable.
