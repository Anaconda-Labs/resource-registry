# Badge Snippet for Resource README

Add this badge to the top of your resource's README.md file (right after the title):

```markdown
[![Status](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Anaconda-Labs/REPO_NAME/main/.github/badges/status.json?0&cacheSeconds=300)](https://github.com/Anaconda-Labs/REPO_NAME)
```

**Important:** Replace `REPO_NAME` with your actual repository name in both URLs.

## Example

For a repo named `my-awesome-tutorial`, the badge would be:

```markdown
[![Status](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Anaconda-Labs/my-awesome-tutorial/main/.github/badges/status.json?0&cacheSeconds=300)](https://github.com/Anaconda-Labs/my-awesome-tutorial)
```

## Badge States

- 🟢 **active** - Resource tested within last 90 days
- 🟠 **needs review** - Flagged by lifecycle engine
- ⚪ **archived** - No longer maintained
