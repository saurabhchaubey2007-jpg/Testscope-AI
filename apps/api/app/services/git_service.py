"""Git/GitHub helpers: cloning repositories, checking out refs, PR comments."""
import hashlib
import base64
import hmac
import os
import re
import subprocess

import httpx

from apps.api.app.core.config import settings

GITHUB_URL_RE = re.compile(r"^https://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$")


class GitError(Exception):
    pass


def parse_github_url(url: str) -> tuple[str, str]:
    m = GITHUB_URL_RE.match(url.strip())
    if not m:
        raise GitError("Only https://github.com/<owner>/<repo> URLs are supported")
    return m.group("owner"), m.group("repo")


def clone_dir_for(project_id: str) -> str:
    return os.path.abspath(os.path.join(settings.workspace_dir, "repositories", project_id))


def _git(args: list, cwd: str | None = None, token: str | None = None, timeout: int = 180) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if token:
        # Credentials never enter clone URLs, .git/config or FETCH_HEAD.
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
        env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {encoded}"
    try:
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise GitError(f"git {args[0]} timed out")
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip()
        if token:
            msg = msg.replace(token, "***").replace(encoded, "***")
        raise GitError(f"git {args[0]} failed: {msg}")
    return proc.stdout.strip()


def checkout(repo_url: str, dest: str, ref: str | None = None, pr_number: int | None = None,
             token: str | None = None) -> str:
    """Make sure `dest` contains the repo at the requested ref. Returns the HEAD commit SHA.

    ref:       branch name or commit SHA (defaults to the remote default branch)
    pr_number: if given, the PR head (refs/pull/<n>/head) is checked out
    """
    parse_github_url(repo_url)
    url = repo_url

    if not os.path.isdir(os.path.join(dest, ".git")):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        _git(["clone", "--depth", "1", url, dest], token=token)
    # Never leave the token in .git/config
    _git(["remote", "set-url", "origin", repo_url], cwd=dest, token=token)

    if pr_number:
        fetch_ref = f"pull/{pr_number}/head"
    elif ref:
        fetch_ref = ref
    else:
        fetch_ref = "HEAD"

    _git(["fetch", "--depth", "1", url, fetch_ref], cwd=dest, token=token)
    if pr_number and ref and re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        # A PR can advance while queued; run the SHA attached to the webhook.
        _git(["fetch", "--depth", "1", url, ref], cwd=dest, token=token)
    _git(["checkout", "--force", "--detach", "FETCH_HEAD"], cwd=dest, token=token)
    _git(["clean", "-fdx", "-e", ".venv"], cwd=dest, token=token)
    return _git(["rev-parse", "HEAD"], cwd=dest)


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def post_pr_comment(repo_url: str, pr_number: int, token: str, body: str) -> None:
    owner, repo = parse_github_url(repo_url)
    resp = httpx.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"body": body},
        timeout=20,
    )
    resp.raise_for_status()
