# How we work: issues, branches, pull requests

Every change reaches `main` through a pull request (PR). The PR is raised by the team
member the backlog issue is assigned to, and reviewed and merged by the repository owner
(Mini-Project Part-2, items 2c and 2d). GitHub Actions must be green before merging.

## One backlog item, start to finish

```bash
git checkout main
git pull                                   # start from everything merged so far
git checkout -b s1-04-task-create-edit     # one branch per PR

# ... make the change ...

pip install -r requirements.txt -r requirements-dev.txt
pytest                                     # the same checks GitHub Actions runs
flake8 .

git add -A
git commit -m "TMA-F-010, TMA-F-011: create and edit tasks"
git push -u origin s1-04-task-create-edit
```

`git push` prints a link: open it, then **Create pull request**. In the description write one
`Closes #N` line for every backlog issue the PR finishes (the issue numbers are on the
Issues tab). When the PR is merged, GitHub closes those issues automatically.

## Reviewing and merging (repository owner)

1. Wait for the **CI** and **PR checks** workflows to show green ticks.
2. Read the **Files changed** tab. For screen changes, pull the branch and run `python run.py`.
3. **Review changes > Approve**, then **Merge pull request** with **Create a merge commit**,
   then **Delete branch**.

The owner cannot approve their own PR on GitHub: another member approves it, and the owner merges.

## One-time repository settings (owner)

* **Settings > Branches > Add branch protection rule**, branch name pattern `main`:
  * Require a pull request before merging (Require approvals: 1, Require review from Code Owners)
  * Require status checks to pass: `Lint (flake8)`, `Tests (Python 3.12)`,
    `Linked issue and assignee`
* **Settings > Actions > General > Workflow permissions**: *Read and write permissions*
  (lets the PR-checks workflow assign, label and comment).

## Commit messages

`<Requirement IDs>: <what changed>`, for example
`TMA-F-012, TMA-F-013: delete with confirmation, complete and reopen tasks`.

## Development freeze (end of Sprint 2)

When the last Sprint 2 PR is merged, `main` is tagged `v1.0` and development stops:

```bash
git checkout main && git pull
git tag -a v1.0 -m "Task Manager v1.0 - end of Sprint 2, development frozen"
git push origin v1.0
```

The tag marks the exact code shown at the final demo. A fix after the freeze would need
its own PR and a new tag (`v1.0.1`).
