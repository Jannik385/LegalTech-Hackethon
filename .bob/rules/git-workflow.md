# Git Workflow Rules

## 1. Always Push After a Change
After every code change that results in a commit, immediately push it to the remote repository. Never leave committed changes unpushed.

## 2. Branch-First Workflow — No Direct Pushes to `main`
All changes must go through a feature branch before reaching `main`:

1. **Create a feature branch** for the change (e.g. `feature/short-description` or `fix/short-description`).
2. **Commit and push** the changes to that feature branch.
3. **Wait for the user to test** the branch before merging.
4. **Merge into `main`** only after the user explicitly confirms the changes are working and approved.

Never push directly to `main`. Never merge without user approval.
