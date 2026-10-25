"""
GitHub bridge for Dynamic Island
Fetches public repository updates, recent commits, and status.
Supports Personal Access Token for notifications and private repos.
"""
import requests
from typing import Dict, Any, List

class GitHubBridge:
    def __init__(self, username: str = "RanuK12", token: str = ""):
        self.username = username
        self.token = token

    def fetch_summary(self) -> Dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DynamicIsland-MiniOffice"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            # Get user info and public repos
            user_url = f"https://api.github.com/users/{self.username}"
            resp_user = requests.get(user_url, headers=headers, timeout=3)
            
            repos_url = f"https://api.github.com/users/{self.username}/repos?sort=updated&per_page=4"
            resp_repos = requests.get(repos_url, headers=headers, timeout=3)

            repos = []
            if resp_repos.status_code == 200:
                for r in resp_repos.json():
                    repos.append({
                        "name": r.get("name"),
                        "stars": r.get("stargazers_count", 0),
                        "forks": r.get("forks_count", 0),
                        "language": r.get("language") or "Code",
                        "url": r.get("html_url")
                    })

            user_data = resp_user.json() if resp_user.status_code == 200 else {}
            
            return {
                "ok": True,
                "username": self.username,
                "public_repos": user_data.get("public_repos", len(repos)),
                "followers": user_data.get("followers", 0),
                "repos": repos
            }
        except Exception:
            return {
                "ok": False,
                "username": self.username,
                "public_repos": 0,
                "followers": 0,
                "repos": []
            }

if __name__ == "__main__":
    gh = GitHubBridge()
    print(gh.fetch_summary())
