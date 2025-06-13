# Release Process

This document describes the **automatic** version synchronization in palabra-ai.

## Automatic Version Sync

This project has **bidirectional synchronization** between versions and tags:

### 1. Change version in pyproject.toml → Auto-creates tag

When you:
```bash
# Edit pyproject.toml: version = "0.1.0" → version = "0.1.1"
git add pyproject.toml
git commit -m "Bump version"
git push
```

GitHub Actions automatically:
- Detects version change
- Creates tag `v0.1.1`
- Triggers release workflow

### 2. Create tag → Auto-updates pyproject.toml

When you:
```bash
git tag v0.2.0
git push origin v0.2.0
```

GitHub Actions automatically:
- Updates `pyproject.toml` to `version = "0.2.0"`
- Commits the change with `[skip-tag]` marker
- Triggers release workflow

## How to Release

### Option 1: Update version in pyproject.toml
1. Edit `pyproject.toml`: change `version = "0.1.0"` to desired version
2. Commit and push
3. Everything else is automatic!

### Option 2: Create a tag
1. Run: `git tag v0.1.1 && git push origin v0.1.1`
2. Everything else is automatic!

### Option 3: Use GitHub UI
1. Go to Releases → "Create a new release"
2. Enter tag like `v0.1.1`
3. Publish release
4. Version in pyproject.toml updates automatically!

## Protection from Infinite Loops

The workflows use `[skip-tag]` marker in commit messages to prevent:
- Version update → creates tag → updates version → creates tag... ❌

## Version Format

- In pyproject.toml: `version = "0.1.0"`
- In git tags: `v0.1.0` (with 'v' prefix)

## Examples

### Patch release via version edit
```bash
# In pyproject.toml: 0.1.0 → 0.1.1
git add pyproject.toml
git commit -m "Fix critical bug"
git push
# Tag v0.1.1 created automatically!
```

### Minor release via tag
```bash
git tag v0.2.0 -m "Add new feature"
git push origin v0.2.0
# pyproject.toml updated to 0.2.0 automatically!
```

### Major release via GitHub UI
1. Go to "Releases" → "Draft a new release"
2. Tag version: `v1.0.0`
3. Click "Publish release"
4. pyproject.toml updated to 1.0.0 automatically!

## Troubleshooting

- **Tag not created?** Check if commit message contains `[skip-tag]`
- **Version not updated?** Check if tag format is correct (`v` prefix required)
- **Workflows not running?** Check Actions tab for errors
