---
description: List or delete old wip/* branches. Default retention 90 days.
disable-model-invocation: true
---

List or delete WIP branches older than the retention threshold.

To list: `git branch --list 'wip/*' --sort=-committerdate`

To prune: `git branch --list 'wip/*' --sort=committerdate | while read b; do
  age_days=$(( ($(date +%s) - $(git log -1 --format=%ct "$b")) / 86400 ))
  if [ "$age_days" -gt "${RETENTION_DAYS:-90}" ]; then
    echo "Deleting $b (age: ${age_days}d)"
    git branch -D "$b"
  fi
done`

Confirm with the user before bulk deletion.
