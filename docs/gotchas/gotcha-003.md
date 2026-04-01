## 003 — Symlinked repo exposing shared mutable state

**Date discovered:** 2026-03-23  
**Severity:** Functional  
**Components:** /opt/splinter, user home directories, symlinks

**Symptoms:**
OK, this is a dumb one...

After symlinking `/opt/splinter` into team members' home directories, one user made changes that were immediately visible to all other users. Edits to config files, `.env`, and other repo contents had no isolation. Any user could unintentionally affect the shared production deployment.

**Root cause:**
Symlinks don't copy files - they point to the same location. All users were editing the same files in `/opt/splinter`. This is by design, and was initially the goal (shared management of a single deployment). In practice, having multiple people able to silently mutate production config without coordination was uncomfortable and error-prone.

**Fix applied:**
Removed all symlinks from user home directories. Each team member cloned the repo locally into their own home directory. `/opt/splinter` remains the canonical production deployment, and changes are coordinated through git rather than direct file editing.

**Considered but deferred:**
- **Keep symlinks with file permissions** — restrict write access so only one user can edit. Too rigid, and doesn't solve the coordination problem.
- **Symlinks with git-based deployment** — users edit in their own clones and deploy to `/opt/splinter` via a script. Adds process overhead that wasn't justified yet.
- **Shared group write access with communication norms** — relies on human discipline to avoid conflicts. Not reliable enough for production config.

**Lesson:**
Symlinks are pointers, not copies. Shared write access to production config requires explicit coordination (version control, review, deploy scripts), not just filesystem access. When in doubt, give each user their own working copy and use git as the integration point.