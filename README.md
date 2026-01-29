# gha-validator

**GitHub Actions Workflow Validator** - Catch semantic issues before you push.

## The Problem

GitHub Actions workflows fail for frustrating reasons:
- Syntax errors only discovered after pushing
- Triggers that look right but never fire
- Missing version tags on actions
- Reusable workflows without refs
- Permissions configured incorrectly

Stack Overflow is full of "why isn't my workflow running?" questions. This tool catches those issues *before* you commit.

## The Solution

`gha-validator` validates your `.github/workflows/*.yml` files locally and catches both syntax errors and semantic gotchas that GitHub won't tell you about until it's too late.

## Installation

```bash
pip install gha-validator
```

Or run directly:

```bash
pip install PyYAML
chmod +x gha_validator.py
./gha_validator.py .github/workflows
```

## Usage

### Validate all workflows in a directory

```bash
gha-validator .github/workflows
```

### Validate a single workflow file

```bash
gha-validator .github/workflows/ci.yml
```

### Strict mode (warnings = errors)

```bash
gha-validator --strict .github/workflows
```

### Quiet mode (errors and warnings only)

```bash
gha-validator --quiet .github/workflows
```

## Example Output

Running on a problematic workflow:

```bash
$ gha-validator examples/.github/workflows/bad-workflow.yml

🔍 Found 4 issue(s) in 1 workflow file(s):

ℹ️ INFO: examples/.github/workflows/bad-workflow.yml [on.workflow_dispatch]
  workflow_dispatch requires workflow to exist on default branch to appear in UI

❌ ERROR: examples/.github/workflows/bad-workflow.yml [jobs.build]
  Job "build" missing "runs-on" (required for normal jobs)

⚠️ WARNING: examples/.github/workflows/bad-workflow.yml [jobs.build.steps[0].uses]
  Job "build", step 1: Action "actions/checkout" missing version tag (e.g., @v1)

ℹ️ INFO: examples/.github/workflows/bad-workflow.yml [jobs.deploy.uses]
  Job "deploy" uses local reusable workflow - ensure it exists
```

## What It Checks

### Syntax & Structure
- ✅ Valid YAML syntax
- ✅ Required `on` and `jobs` sections
- ✅ Job structure (runs-on, steps, etc.)

### Triggers
- ✅ Empty trigger configurations
- ✅ workflow_dispatch visibility (requires default branch)
- ✅ pull_request default behavior
- ✅ Common trigger misconfigurations

### Jobs & Steps
- ✅ Missing `runs-on` for normal jobs
- ✅ Actions without version tags (@v1, @v2, etc.)
- ✅ Reusable workflows missing version/ref

### Permissions
- ✅ Valid permission scopes
- ✅ Valid permission levels (read/write/none)
- ✅ Unknown permission keys

## Use Cases

### Pre-commit hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/sh
if [ -d ".github/workflows" ]; then
    gha-validator .github/workflows || exit 1
fi
```

### CI/CD validation

```yaml
- name: Validate workflows
  run: |
    pip install gha-validator
    gha-validator .github/workflows
```

### Local development

```bash
# Check before committing
gha-validator .github/workflows

# Watch mode (requires entr or similar)
ls .github/workflows/*.yml | entr gha-validator .github/workflows
```

## Why Not Just Use actionlint?

`actionlint` is great for syntax. This tool focuses on *semantic* issues:

- **actionlint**: "Your YAML is valid"
- **gha-validator**: "Your YAML is valid but workflow_dispatch won't show up in the UI until you merge to main"

Use both for maximum confidence.

## Roadmap

- [ ] More trigger validations (schedule cron syntax, etc.)
- [ ] Workflow graph analysis (circular dependencies)
- [ ] Action marketplace validation (does the action exist?)
- [ ] Integration with gh CLI
- [ ] Auto-fix suggestions

## Contributing

PRs welcome! Some ideas:
- Add more common gotchas from Stack Overflow
- Support for composite actions validation
- Better error messages with docs links
- VS Code extension integration

## License

MIT
