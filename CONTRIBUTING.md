# Contributing to GRaCEmo ViRa

## 📌 Development Philosophy
1. **The Kernel is Boring**: The core daemon only routes events, verifies state, and persists memory. Intelligence stays in adapters and external agents.
2. **Adapters are Independent**: Each adapter (Vision, Voice, Bridge) is a decoupled process interacting only via HTTP/SSE or Unix Sockets.
3. **No Direct Hardcodes**: All tunable parameters, thresholds, and paths must live in `config/*.yaml` or `config/*.toml`.

---

## 🔀 Git Branching & Workflow

We follow **Trunk-Based Development**:
- `main` branch is always stable and runnable.
- Feature branches are short-lived (`feat/<name>`, `fix/<name>`, `docs/<name>`).
- Merge to `main` via Pull Requests with Squash Merge.

---

## 📝 Conventional Commits

Commit messages must follow the standard format:
```text
<type>(<optional scope>): <description>
```

**Allowed Types:**
- `feat`: New feature or capability
- `fix`: Bug fix
- `docs`: Documentation updates
- `refactor`: Code restructures without behavioral change
- `test`: Adding or updating test suites
- `ci`: CI/CD configurations
- `chore`: Dependency updates or build adjustments
