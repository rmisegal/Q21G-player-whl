# CLAUDE.md
**IMPORTANT: Read this entire file before making ANY code changes.**
Version: 1.0.0

## Development Principles

1. **Ask clarifying questions** — Always ask as many questions as needed before implementing. Never assume.
2. **Check existing code first** — Before implementing any function or system, search the current codebase to see if it already exists.
3. **Reuse existing code above all else** — Prefer wiring into existing functions and modules. This ensures easy integration.
4. **Recommend session splits** — If a task is too large for one session, recommend splitting it up.
5. **Modularity** — The project must be as modular as possible. Small, focused modules with clear responsibilities.
6. **TDD** — Follow Test-Driven Development. Write tests first, then implement to make them pass.
7. **150-line file limit** — All Python files must stay under 150 lines. If a file exceeds this, refactor or split it.
8. **No hardcoded secrets or paths** — Never hardcode secrets, credentials, file paths, URLs, or environment-specific values in source code. All such values must come from `config.json` or environment variables.

## Documentation & Versioning

1. **Document versioning** — All documentation files (README, PRDs, plans) must have a semantic version (e.g., `1.0.0`) at the top.
2. **Code-to-PRD mapping** — Every source file must have a header comment indicating its area/system and corresponding PRD:
   ```python
   # Area: <Feature Name>
   # PRD: docs/<prd-filename>.md
   ```
3. **Sync requirement** — When code changes, update the corresponding PRD:
   - Increment the PRD version
   - Update the PRD content to match the implementation
   - Update any affected README sections
4. **PRD location** — All PRD documents live in the `docs/` folder.

## Feature PRDs

| Feature | PRD | Modules |
|---------|-----|---------|
| RLGM (League Manager Interface) | `docs/prd-rlgm.md` | `_infra/rlgm/` |
| GMC (Game Manager Component) | `docs/prd-rlgm.md` | `_infra/gmc/` |
| Player API | `docs/prd-player-api.md` | `api/` |
| Configuration | `docs/prd-configuration.md` | `_infra/shared/config/` |
| State Management | `docs/prd-state-management.md` | `_infra/repository/` |

## Project Structure

```
q21-player-sdk/
├── CLAUDE.md                    # This file - development guidelines
├── README.md                    # Quick start guide
├── CONFIG_GUIDE.md              # Configuration documentation
├── docs/
│   ├── prd-rlgm.md             # RLGM architecture PRD
│   └── comparison-*.md          # Implementation comparisons
├── js/
│   └── config.json              # Configuration file
├── my_player.py                 # Student implementation (PUBLIC)
└── dist/
    └── q21_player-*.whl         # SDK package (hidden infrastructure)
```

## Terminology

| Term | Full Name | Description |
|------|-----------|-------------|
| **GMC** | Game Manager Component | Handles a single Q21 game cycle with the referee |
| **RLGM** | Referee-League Game Manager | Interfaces between League Manager and GMC |
| **GPRM** | Game Parameters | Input data needed to run a single game |
| **PlayerAI** | Player AI Interface | The 4 callbacks students implement |
