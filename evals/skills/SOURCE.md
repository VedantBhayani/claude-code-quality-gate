# Vendored skills: source

Copied verbatim from [kenny589/gtm-flywheel](https://github.com/kenny589/gtm-flywheel) at commit
`ba67446418663737a00274819dc2bf68c0da2c31` (2026-02-17), under the MIT licence in [LICENSE](LICENSE)
(Copyright (c) 2026 ColdIQ). Nothing in these files has been edited.

| Here | Upstream path | Git blob |
|---|---|---|
| `intent-signals/SKILL.md` | `signal-scoring/intent-signals/SKILL.md` | `dd48ddc120ee37de1a4eb27d7adf0e6cfed1ae21` |
| `trigger-mapping/SKILL.md` | `signal-scoring/trigger-mapping/SKILL.md` | `66dc1c89bfb36bf0d0922c5d27c028730103cb58` |
| `lead-prioritization/SKILL.md` | `signal-scoring/lead-prioritization/SKILL.md` | `41574988bae629eab65b3aaeb310bc4ebba181eb` |
| `copy-frameworks/SKILL.md` | `cold-email/copy-frameworks/SKILL.md` | `cdbb885d9302d77fee03d350a29c74259907a540` |
| `LICENSE` | `LICENSE` | `eabcaca492e78595629a925f5fa39918f7b2ed5d` |

The blob IDs are the upstream ones and match these files byte-for-byte (LF line endings). A
Windows checkout with `core.autocrlf=true` shows CRLF; `quality_gate.skill_rules.prepare_skill`
normalises to LF before hashing, so the recorded skill hash is the same on every platform.

What a run gets: `prepare_skill(path).text` (any `model:` key removed from the frontmatter; these
four files have none), injected with `--append-system-prompt-file`. Its SHA-256 is the skill hash
on every run record.
