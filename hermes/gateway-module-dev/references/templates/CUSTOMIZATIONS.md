# Customizations

Track every intentional gateway source customization made by this module.

## Module

- Module name: `MODULE_NAME`
- Supported gateway versions: `vX.Y`
- Last audited: `YYYY-MM-DD`
- Apply order source: `patches/<version>/series`

## Summary

| Patch | Responsibility | Gateway files touched | User-visible goal | Risk |
|---|---|---|---|---|
| `001-example.patch` | Short responsibility | `gateway/...` | Describe the visible behavior | Low/Med/High |

## Patch Details

### `001-example.patch`

- Responsibility:
- Gateway files:
- Insertion points:
- User-visible behavior:
- Verification coverage:
- Upgrade hazards:
- Rollback notes:

## Hooks

| Hook | Purpose | Installed by | Removed by | Verification |
|---|---|---|---|---|
| `MODULE_NAME` | Describe hook purpose | `scripts/install.sh` | `scripts/uninstall.sh` | Describe behavior test |

## Environment and Profile Markers

| Marker | Purpose | Created by | Removed by | Notes |
|---|---|---|---|---|
| `# MODULE_NAME begin` | Example profile block | `scripts/install.sh` | `scripts/uninstall.sh` | Keep marker names unique |

## Upgrade Protocol

1. Start from clean upstream gateway source for the target version.
2. Create or update `patches/<version>/`.
3. Put patch filenames in `patches/<version>/series`.
4. Run `git apply --check` for each patch in series order.
5. Run `scripts/check-consistency.sh`.
6. Run `scripts/verify.sh` against an installed test gateway.
7. Update this file and `IMPACT_MATRIX.md`.
