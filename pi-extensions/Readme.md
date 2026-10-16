# pi-extensions

Pi extensions used with this project.

## beads-prime

Moved to the standalone package
[`@maphew/pi-beads`](https://github.com/maphew/pi-beads), so it can be installed
on every machine:

```bash
pi install git:github.com/maphew/pi-beads
```

The extension injects live `bd prime` workflow context and git-authority policy
into pi's system prompt, and no-ops outside a `.beads/` workspace. See the
package README for behavior and configuration. This directory is kept only as a
pointer to that package.
