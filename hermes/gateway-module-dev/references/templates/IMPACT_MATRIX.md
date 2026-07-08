# Impact Matrix

Use this table before and after every gateway module change. A checked column means the file or behavior must be updated or explicitly reviewed.

| Change type | install.sh | update.sh | uninstall.sh | verify.sh | check-consistency.sh | SKILL.md | CUSTOMIZATIONS.md |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Add patch | yes | yes | no | yes | yes | yes | yes |
| Remove patch | yes | yes | yes | yes | yes | yes | yes |
| Reorder patches | yes | yes | no | yes | yes | yes | yes |
| Add hook | yes | no | yes | yes | yes | yes | yes |
| Remove hook | yes | no | yes | yes | yes | yes | yes |
| Add env var/profile marker | yes | no | yes | yes | yes | yes | yes |
| Remove env var/profile marker | yes | no | yes | yes | yes | yes | yes |
| Change gateway behavior | no | no | no | yes | no | yes | yes |
| Add supported Hermes version | yes | yes | no | yes | yes | yes | yes |
| Drop supported Hermes version | yes | yes | no | yes | yes | yes | yes |
| Change lifecycle script logic | yes | yes | yes | yes | yes | yes | no |

## Rules

- Check this matrix before editing.
- After editing, update every checked artifact or record why no change is needed.
- Keep change types generic; add module-specific rows only when they represent stable recurring maintenance categories.
- Do not use this table as a substitute for behavior tests.
