# Glossary

**Signal**: an observable, dated change at a company that suggests it may buy now. In this project, usually an open sales job post.
_Avoid_: lead, intent (on its own)

**Collection date**: the day a job post was fetched. A signal's age is measured from this date.

**Freshness window**: how long after its post date a signal still counts as fresh enough to contact.

**Ambiguous role**: a job title where it's unclear whether it signals sales investment (e.g. Account Manager, Customer Success Manager, Solutions Engineer).

**Model switch**: running the same skill on a different model (e.g. Haiku vs Sonnet).
_Avoid_: drift (for this)

**Model upgrade**: running the same skill on a newer version of the same model.

**Flip rate**: the share of items whose label changes between two models, or between two versions of one model.

**Repeat noise**: the share of items whose label changes between two runs of the *same* model on the *same* input.

**Task**: a named piece of work with its own spend budget. It can span several Claude Code sessions. Unlabelled work counts as one session.
_Avoid_: session (when you mean the piece of work)

**Spend cap**: the budget at which a task is stopped.
