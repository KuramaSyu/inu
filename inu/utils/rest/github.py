from typing import *

import aiohttp
from datetime import datetime
import asyncio

OWNER = "zp33dy"
REPO = "inu"

class Commit:
    DEFAULT_KEYWORDS: List[str] = [
        "FEATURE",
        "FIX",
        "REFACTOR",
        "REMOVED",
        "ADDED",
    ]
    def __init__(self, commit_data: dict):
        self.author: str = commit_data["author"]["name"]
        self.message: str = commit_data["message"]
        self.title: str = self.extract_title(commit_data["message"])
        self.description: str = self.extract_description(commit_data["message"])
        # convert date to datetime object
        self.date: datetime = datetime.strptime(
            commit_data["author"]["date"], 
            "%Y-%m-%dT%H:%M:%SZ"
        )
        
    def extract_title(self, message: str) -> str:
        lines: List[str] = message.split("\n")
        if lines:
            return lines[0].strip()
        else:
            return ""

    def date_string(self) -> str:
        """
        Format: YYYY-MM-DD HH:MM:SS
        """
        return self.date.strftime("%Y-%m-%d %H:%M:%S")

    def extract_description(self, message: str) -> str:
        lines: List[str] = message.split("\n")
        if len(lines) > 1:
            return "\n".join(lines[1:]).strip()
        else:
            return ""

    def __str__(self) -> str:
        return f"Author: {self.author}\nMessage: {self.message}\nDescription: {self.description}\nDate: {self.date}\n------------------------------"
    
    def has_keywords(self, keywords: List[str]) -> bool:
        for keyword in keywords:
            if keyword in self.message:
                return True
        return False



class GitHubAPI:
    def __init__(self, owner: str, repo: str):
        self.owner: str = owner
        self.repo: str = repo
        self.base_url: str = "https://api.github.com"

    @staticmethod
    def INU_REPO() -> "GitHubAPI":
        return GitHubAPI(OWNER, REPO)

    async def fetch_commits(self) -> List[Commit]:
        commits: List[Commit] = []
        page: int = 1
        per_page: int = 200

        url: str = f"{self.base_url}/repos/{self.owner}/{self.repo}/commits"
        params: dict = {
            "page": page,
            "per_page": per_page
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    commits_data: List[dict] = await response.json()
                    if len(commits_data) == 0:
                        return commits
                    for commit_data in commits_data:
                        commit: Commit = Commit(commit_data["commit"])
                        commits.append(commit)
        return commits

async def main():
    # Specify the repository details
    owner = "zp33dy"
    repo = "inu"

    # Create an instance of GitHubAPI
    github_api = GitHubAPI(owner, repo)

    # Get the last commits
    commits = await github_api.fetch_commits()

    # Print the commit details
    for commit in commits:
        print(commit)

# Run the main function
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
