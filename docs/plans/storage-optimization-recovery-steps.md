# Storage Optimization - System Recovery Steps

## After System Restart

Once your system is back up and bash is working, here are the exact commands to run:

### 1. Verify Git Status
```bash
cd /home/sergeblumenfeld/podcastknowledge
git status
```

### 2. If Files Are Not Staged, Stage Them:
```bash
# Stage the plan update
git add docs/plans/storage-optimization-cleanup-plan.md

# Stage the tmp file deletions
git add -u transcriber/data/checkpoints/

# Stage the log deletions and additions
git add -u transcriber/logs/
git add transcriber/logs/*.gz

# Stage the new documentation
git add docs/plans/storage-optimization-phase2-progress.md
git add docs/plans/storage-optimization-git-status.md
git add docs/plans/phase2-files-changed.txt
git add docs/plans/storage-optimization-recovery-steps.md
```

### 3. Commit Phase 2
```bash
git commit -m "Phase 2: Clean temporary and log files

- Removed 42 empty .tmp files from checkpoints directory
- Archived large podcast_transcriber logs with gzip (saved ~6.4 MB)
- Removed old error logs (saved ~346 KB)
- Total storage reduction: ~6.75 MB
- Log directory reduced from 6.7MB to 288KB

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 4. Verify Storage Reduction
```bash
du -sh /home/sergeblumenfeld/podcastknowledge
```

Expected: Around 68 MB (down from 1.057 GB)

### 5. Ready for Phase 3
Once committed, we can proceed with Phase 3: Consolidate Test Artifacts

## Alternative Recovery Options

If restarting doesn't fix the issue:

1. **Recreate /tmp permissions:**
   ```bash
   sudo mkdir -p /tmp
   sudo chmod 1777 /tmp
   sudo chown root:root /tmp
   ```

2. **Check for other affected services:**
   ```bash
   systemctl status
   ```

3. **Recreate common /tmp subdirectories:**
   ```bash
   sudo mkdir -p /tmp/.X11-unix
   sudo chmod 1777 /tmp/.X11-unix
   ```

## Important Notes
- The project files are safe - we only removed project-specific temporary files
- All changes are documented in the `docs/plans/` directory
- The actual cleanup work is complete, we just need to commit it