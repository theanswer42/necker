---
description: Implement a feature or fix from a TODO item, GitHub issue, or free-text description
---

# Implement Feature/Fix

You are implementing a well-defined feature or code change. The input is: $ARGUMENTS

## Step 1: Identify the work item

Determine the source of the work item:

- **TODO.md item**: Search TODO.md for a title substring match against the input. Read the matched item's full description.
- **GitHub issue** (e.g., `#42` or a GitHub URL): Use `gh issue view` to read the issue title, body, and comments.
- **Free text description**: Use the input directly as the work description.

If the input is ambiguous or matches multiple items, ask the user to clarify before proceeding.

## Step 2: Understand scope and explore code

1. Read and understand the work item fully.
2. Explore the relevant parts of the codebase to understand what needs to change.
3. Identify which files will be modified or created.
4. Consider architectural implications:
   - Does this change affect the data model?
   - Does it introduce new dependencies?
   - Does it change any public interfaces?
   - Are there edge cases or risks?

## Step 3: Align with the user

Present a brief implementation plan:
- What you'll change and why
- Any architectural concerns or trade-offs
- What tests you'll write
- Anything you're unsure about

**Use your judgment as a senior engineer:**
- For straightforward, low-risk changes (e.g., adding a dependency, fixing a clear bug): state the plan, document it, and proceed to step 4 without waiting for confirmation.
- For changes with architectural implications, ambiguity, or multiple valid approaches: **wait for the user to confirm or adjust the plan before proceeding.**

Document the plan regardless:
- **If the source is a GitHub issue**: Add a comment to the issue summarizing the implementation plan using `gh issue comment`.
- **If the source is TODO.md**: Update the TODO item in TODO.md to include the implementation plan as a sub-bullet.

If the plan changes during implementation (e.g., you discover something unexpected), update the documentation accordingly.

## Step 4: Create a branch

Create a new branch from `main`. Use `fix/` prefix for bug fixes and `feat/` for new functionality:
- From TODO: `fix/<short-kebab-description>` or `feat/<short-kebab-description>` (e.g., `fix/bulk-create-rowcount`, `feat/add-pydantic-deps`)
- From GitHub issue: `fix/<issue-number>-<short-kebab-description>` or `feat/<issue-number>-<short-kebab-description>`
- From free text: same convention

```bash
git checkout main && git pull && git checkout -b <branch-name>
```

## Step 5: Implement the change

Write the code. Follow existing patterns and conventions in the codebase. Keep changes focused on the work item — do not refactor surrounding code or add unrelated improvements.

## Step 6: Write tests

Write or update tests for the changes:
- Place tests in the appropriate `tests/` directory, following existing test file naming conventions.
- Test both the happy path and meaningful edge cases.
- Run the tests to ensure they pass:

```bash
uv run pytest tests/ -x -v
```

If tests fail, fix the code and re-run until they pass.

## Step 7: Lint and format

Run the pre-commit checks (this is mandatory — do not skip):

```bash
uv run ruff format .
uv run ruff check .
```

Fix any issues reported by `ruff check` before proceeding.

## Step 8: Commit

Create a commit with a clear message that references the work item:
- For TODO items: reference the item title
- For GitHub issues: include `Fixes #<number>` or `Closes #<number>` in the commit body
- **Important**: If the change modified `pyproject.toml` (dependency changes), always include `uv.lock` in the commit.

## Step 9: Update the work item

- **TODO.md**: Check off the item (`- [x]`).
- **GitHub issue**: The `Fixes #N` in the commit/PR will auto-close it.

## Step 10: Push and create a PR

```bash
git push -u origin <branch-name>
```

Create a pull request using `gh pr create`. The PR should:
- Have a clear, concise title
- Reference the TODO item or GitHub issue
- Summarize what was changed and why
- Include a test plan

```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<what changed and why>

## References
<link to TODO item or "Fixes #N">

## Test plan
<how to verify the change>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Return the PR URL to the user.
