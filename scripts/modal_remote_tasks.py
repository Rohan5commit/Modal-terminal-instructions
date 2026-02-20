import os
import subprocess

import modal

APP_NAME = os.getenv("MODAL_REMOTE_APP_NAME", "modal-remote-task-runner")
DEFAULT_REPO_URL = os.getenv("MODAL_REMOTE_REPO_URL", "")
DEFAULT_BRANCH = os.getenv("MODAL_REMOTE_REPO_BRANCH", "main")
DEFAULT_CMD = os.getenv("MODAL_DEFAULT_CMD", "echo modal-ready")
DEFAULT_PUSH = int(os.getenv("MODAL_REMOTE_PUSH", "0"))
DEFAULT_COMMIT_MESSAGE = os.getenv("MODAL_REMOTE_COMMIT_MESSAGE", "modal remote update")

CPU = float(os.getenv("MODAL_CPU", "6"))
MEMORY_MB = int(os.getenv("MODAL_MEMORY_MB", str(14 * 1024)))
TIMEOUT_SECONDS = int(os.getenv("MODAL_TIMEOUT_SECONDS", str(60 * 60)))

REPO_PATH = "/root/repo"
DEFAULT_SECRET = modal.Secret.from_name("github-token")

image = modal.Image.debian_slim().apt_install("bash", "ca-certificates", "git")
app = modal.App(APP_NAME)


def _repo_url_with_token(repo_url: str) -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        return repo_url
    if repo_url.startswith("https://x-access-token:"):
        return repo_url
    if repo_url.startswith("https://github.com/"):
        return repo_url.replace("https://github.com/", f"https://x-access-token:{token}@github.com/", 1)
    return repo_url


@app.function(image=image, cpu=CPU, memory=MEMORY_MB, timeout=TIMEOUT_SECONDS, secrets=[DEFAULT_SECRET])
def run_remote_cmd(
    repo_url: str,
    cmd: str,
    branch: str = "main",
    push: bool = False,
    commit_message: str = "modal remote update",
) -> None:
    if not repo_url:
        raise ValueError("repo_url is required.")

    env = os.environ.copy()
    env["IN_MODAL_TASK_RUNNER"] = "1"

    auth_repo_url = _repo_url_with_token(repo_url)
    clone_args = ["git", "clone", "--depth", "1"]
    if branch:
        clone_args += ["--branch", branch]
    clone_args += [auth_repo_url, REPO_PATH]
    subprocess.run(clone_args, check=True, env=env)

    subprocess.run(["bash", "-lc", cmd], check=True, cwd=REPO_PATH, env=env)

    if not push:
        return

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        cwd=REPO_PATH,
        env=env,
        capture_output=True,
        text=True,
    ).stdout.strip()

    if not status:
        return

    git_name = os.getenv("GIT_AUTHOR_NAME", "Modal Agent Runner")
    git_email = os.getenv("GIT_AUTHOR_EMAIL", "modal-agent@users.noreply.github.com")
    subprocess.run(["git", "config", "user.name", git_name], check=True, cwd=REPO_PATH, env=env)
    subprocess.run(["git", "config", "user.email", git_email], check=True, cwd=REPO_PATH, env=env)
    subprocess.run(["git", "add", "-A"], check=True, cwd=REPO_PATH, env=env)
    subprocess.run(["git", "commit", "-m", commit_message], check=True, cwd=REPO_PATH, env=env)

    if auth_repo_url != repo_url:
        subprocess.run(["git", "remote", "set-url", "origin", auth_repo_url], check=True, cwd=REPO_PATH, env=env)

    target_branch = branch or "main"
    subprocess.run(["git", "push", "origin", f"HEAD:{target_branch}"], check=True, cwd=REPO_PATH, env=env)


@app.local_entrypoint()
def main(
    cmd: str = DEFAULT_CMD,
    repo_url: str = DEFAULT_REPO_URL,
    branch: str = DEFAULT_BRANCH,
    push: int = DEFAULT_PUSH,
    commit_message: str = DEFAULT_COMMIT_MESSAGE,
) -> None:
    push_enabled = bool(push)
    run_remote_cmd.remote(repo_url=repo_url, cmd=cmd, branch=branch, push=push_enabled, commit_message=commit_message)
