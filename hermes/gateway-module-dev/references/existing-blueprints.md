# Existing Blueprint References

This skill abstracts the gateway module paradigm from two reference artifacts:

- `/home/vive/Work/Hermes/2026-07-07-gateway-module-blueprint/gateway-module-paradigm.md` on `vive@192.168.125.12`
- `/opt/data/skills/hermes-wechat-enhance/references/development-blueprint.md`

Use those references only as case studies. The reusable pattern is:

- Hermes regular skills add knowledge; gateway modules modify gateway source behavior.
- Source edits require reversible Git anchoring, not only file copying.
- Patches are selected by detected Hermes/gateway version.
- Install/update/uninstall scripts must be lifecycle peers, not independent ad hoc scripts.
- `CUSTOMIZATIONS.md` records what changed and why.
- `IMPACT_MATRIX.md` records what must be checked when a change type occurs.
- `verify.sh` validates user-visible goals, not implementation existence.
- `check-consistency.sh` catches drift between patch files, series files, docs, hooks, and lifecycle scripts.

Known reference modules:

- `hermes-wechat-enhance`: first concrete gateway-module style case. It is useful for seeing lifecycle pressure, but its patch count, patch order, and WeChat-specific behavior are not part of this standard.
- `hermes-alive`: candidate for migration into gateway-module style when it needs lifecycle-managed gateway integration.
