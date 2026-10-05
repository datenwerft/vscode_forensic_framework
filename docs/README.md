# Forensic Evidence Workspace

Product planning and technical experiments for a VS Code forensic evidence workspace.

- [Product concept](forensic-framework-product-paper.md)
- [E01 access results](verification/e01-access/README.md)
- [Native macOS write-boundary results](verification/e01-access/MACOS-READONLY.md)
- [Windows/WSL validation instructions](verification/e01-access/WSL.md)

This repository currently contains documentation and disposable probes, not a
production VS Code extension. macOS and one Debian Linux package combination have
passed the recorded access tests; Windows/WSL remains untested.

The small synthetic segmented E01 reference is committed so another machine can
read the exact same bytes. Generated test runs are ignored. Do not add actual
case evidence to this repository.

Project-local BMad skills and configuration are included. The `.claude/skills`
entries are relative symlinks to `.agents/skills`; cloning within WSL preserves
normal Linux symlink behavior. The probes themselves do not depend on these links.

Run verification commands from the repository root. Scripts, fixtures, and JSON
results live in `_verification/`; BMad tooling lives in `.agents/` and `_bmad/`.
