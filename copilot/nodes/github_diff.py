"""GitHub deploy-diff node — flag risky changes in the most recent deploy.

Optional: needs ``GITHUB_TOKEN`` + ``GITHUB_REPO`` and the ``github`` extra
(PyGithub). If either is missing, it degrades gracefully to an info-level note so
the rest of the investigation still runs.
"""

from __future__ import annotations

import os

from ..deps import Deps
from ..llm import SONNET
from ..state import Evidence, State

DIFF_SYS = """You review the diff of the most recent deploy to a service that is
now having an incident. Flag changes that plausibly cause latency or errors:
N+1 / unbounded DB queries, new synchronous/blocking calls, removed caching,
changed timeouts or pool sizes, risky config/migration changes. Name the file and
the specific risk. If nothing looks risky, say so plainly."""


def make_github_node(deps: Deps):
    def run(state: State) -> dict:
        repo_name = os.getenv("GITHUB_REPO")
        token = os.getenv("GITHUB_TOKEN")
        if not (repo_name and token):
            return {"evidence": [Evidence(source="github", summary="GitHub not configured; skipped deploy diff.", severity="info")]}

        try:
            from github import Github  # type: ignore

            gh = Github(token)
            repo = gh.get_repo(repo_name)
            commits = list(repo.get_commits()[:2])
            if len(commits) < 2:
                return {"evidence": [Evidence(source="github", summary="Not enough history to diff.", severity="info")]}
            comparison = repo.compare(commits[1].sha, commits[0].sha)
            patch = "\n".join(
                f"--- {f.filename}\n{f.patch or ''}" for f in comparison.files[:20]
            )[:20000]
        except Exception as e:  # noqa: BLE001
            return {"evidence": [Evidence(source="github", summary=f"GitHub diff failed: {e}", severity="warning")]}

        llm = deps.llm(SONNET, max_tokens=1500)
        summary = llm.invoke([("system", DIFF_SYS), ("human", patch)]).content
        return {
            "evidence": [
                Evidence(
                    source="github",
                    summary=str(summary),
                    detail=f"deploy {commits[0].sha[:8]} vs {commits[1].sha[:8]}",
                    severity="warning",
                )
            ]
        }

    return run
