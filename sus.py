#!/usr/bin/env python3


import os
import sys
import re
import json
import time
import requests
import argparse
import logging
import concurrent.futures
from typing import List, Dict, Any, Tuple, Set, Optional
from pathlib import Path
import base64
import toml
from urllib.parse import quote

import colorama
colorama.init()

COLOR_RED = colorama.Fore.RED
COLOR_YELLOW = colorama.Fore.YELLOW
COLOR_GREEN = colorama.Fore.GREEN
COLOR_BLUE = colorama.Fore.BLUE
COLOR_MAGENTA = colorama.Fore.MAGENTA
COLOR_CYAN = colorama.Fore.CYAN
COLOR_WHITE = colorama.Fore.WHITE
COLOR_RESET = colorama.Style.RESET_ALL


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("supply-chain-analyzer")

class DependencyChecker:
    """Base class for dependency checking implementations."""

    def __init__(self):
        self.suspicious_packages = []
        self.checked_packages = set()  # Cache to avoid redundant checks

    def check_dependency(self, package_name: str, version: str = None) -> bool:
        """Check if a dependency exists in the official repository."""
        raise NotImplementedError("Subclasses must implement this method")

    def get_suspicious_packages(self) -> List[Dict[str, Any]]:
        """Return the list of suspicious packages found."""
        return self.suspicious_packages


class PyPIChecker(DependencyChecker):
    """Checks if Python packages exist in PyPI."""

    def __init__(self):
        super().__init__()
        self.pypi_base_url = "https://pypi.org/pypi"
        self.session = requests.Session()

    def check_dependency(self, package_name: str, version: str = None) -> bool:
        """Check if a Python package exists in PyPI."""
        if package_name in self.checked_packages:
            return True

        url = f"{self.pypi_base_url}/{package_name}/json"

        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                self.checked_packages.add(package_name)
                return True
            else:
                self.suspicious_packages.append({
                    "name": package_name,
                    "version": version,
                    "issue": "Package not found in PyPI",
                    "risk": "High - Potential typosquatting or dependency confusion target"
                })
                return False
        except requests.RequestException as e:
            logger.error(f"Error checking PyPI for {package_name}: {str(e)}")
            return False


class NPMChecker(DependencyChecker):
    """Checks if Node.js packages exist in npm registry."""

    def __init__(self):
        super().__init__()
        self.npm_base_url = "https://registry.npmjs.org"
        self.session = requests.Session()

    def check_dependency(self, package_name: str, version: str = None) -> bool:
        """Check if a Node.js package exists in npm registry."""
        if package_name in self.checked_packages:
            return True

        url = f"{self.npm_base_url}/{package_name}"

        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                self.checked_packages.add(package_name)
                return True
            else:
                self.suspicious_packages.append({
                    "name": package_name,
                    "version": version,
                    "issue": "Package not found in npm registry",
                    "risk": "High - Potential typosquatting or dependency confusion target"
                })
                return False
        except requests.RequestException as e:
            logger.error(f"Error checking npm for {package_name}: {str(e)}")
            return False


class RepositoryClient:
    """Base class for repository API client implementations."""

    def get_repositories(self, owner: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get repositories for a specific owner."""
        raise NotImplementedError("Subclasses must implement this method")

    def search_repositories(self, language: str, min_stars: int = 0, max_stars: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Search for repositories by language and popularity."""
        raise NotImplementedError("Subclasses must implement this method")

    def get_file_content(self, repo_full_name: str, file_path: str) -> str:
        """Get content of a specific file from a repository."""
        raise NotImplementedError("Subclasses must implement this method")

    def search_files(self, repo_full_name: str, file_patterns: List[str]) -> List[str]:
        """Search for files matching patterns in a repository."""
        raise NotImplementedError("Subclasses must implement this method")


class GitHubClient(RepositoryClient):
    """Client for interacting with the GitHub API."""

    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        })

    def _handle_rate_limit(self, response):
        """Handle GitHub API rate limiting."""
        if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
            remaining = int(response.headers['X-RateLimit-Remaining'])
            if remaining == 0:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                current_time = time.time()
                sleep_time = max(1, reset_time - current_time)
                logger.warning(f"{COLOR_YELLOW}Rate limit exceeded. Sleeping for {sleep_time} seconds.{COLOR_RESET}")
                time.sleep(sleep_time)
                return True
        return False

    def get_repositories(self, owner: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get repositories for a specific GitHub user or organization."""
        url = f"{self.base_url}/users/{owner}/repos"
        params = {"per_page": 100}
        all_repos = []

        try:
            while url and len(all_repos) < limit:
                response = self.session.get(url, params=params)

                if self._handle_rate_limit(response):
                    continue

                response.raise_for_status()
                repos = response.json()
                all_repos.extend(repos)

                if 'next' in response.links and len(all_repos) < limit:
                    url = response.links['next']['url']
                    params = {}
                else:
                    url = None

            return all_repos[:limit]
        except requests.RequestException as e:
            logger.error(f"Error fetching repositories for {owner}: {str(e)}")
            return []

    def search_repositories(self, language: str, min_stars: int = 0, max_stars: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Search for repositories by language and popularity with optional max stars."""
        url = f"{self.base_url}/search/repositories"
        query = f"language:{language} stars:>={min_stars}"
        if max_stars is not None:
            query += f" stars:<={max_stars}"

        params = {"q": query, "sort": "stars", "order": "desc", "per_page": 100}
        all_repos = []

        try:
            while url and len(all_repos) < limit:
                response = self.session.get(url, params=params)

                if self._handle_rate_limit(response):
                    continue

                response.raise_for_status()
                search_results = response.json()
                all_repos.extend(search_results.get("items", []))

                if 'next' in response.links and len(all_repos) < limit:
                    url = response.links['next']['url']
                    params = {}
                else:
                    url = None

            return all_repos[:limit]
        except requests.RequestException as e:
            logger.error(f"Error searching repositories for language {language}: {str(e)}")
            return []

    def get_file_content(self, repo_full_name: str, file_path: str) -> str:
        """Get content of a specific file from a GitHub repository."""
        url = f"{self.base_url}/repos/{repo_full_name}/contents/{file_path}"

        try:
            response = self.session.get(url)

            if self._handle_rate_limit(response):
                return self.get_file_content(repo_full_name, file_path)

            if response.status_code == 404:
                return ""

            response.raise_for_status()
            content_data = response.json()

            if content_data.get("encoding") == "base64":
                return base64.b64decode(content_data["content"]).decode("utf-8")
            return ""
        except requests.RequestException as e:
            logger.error(f"Error fetching file {file_path} from {repo_full_name}: {str(e)}")
            return ""
        except UnicodeDecodeError:
            logger.error(f"Error decoding file {file_path} from {repo_full_name}")
            return ""

    def search_files(self, repo_full_name: str, file_patterns: List[str]) -> List[str]:
        """Search for files matching patterns in a GitHub repository."""
        url = f"{self.base_url}/repos/{repo_full_name}"
        try:
            response = self.session.get(url)

            if self._handle_rate_limit(response):
                return self.search_files(repo_full_name, file_patterns)

            response.raise_for_status()
            repo_info = response.json()
            default_branch = repo_info.get("default_branch", "main")

            tree_url = f"{self.base_url}/repos/{repo_full_name}/git/trees/{default_branch}?recursive=1"
            response = self.session.get(tree_url)

            if self._handle_rate_limit(response):
                return self.search_files(repo_full_name, file_patterns)

            if response.status_code == 404:
                tree_url = f"{self.base_url}/repos/{repo_full_name}/git/trees/master?recursive=1"
                response = self.session.get(tree_url)

                if response.status_code == 404:
                    return []

            response.raise_for_status()
            tree_data = response.json()

            if tree_data.get("truncated", False):
                logger.warning(f"Repository tree is truncated for {repo_full_name}. Some files might be missed.")

            matching_files = []
            for item in tree_data.get("tree", []):
                if item["type"] == "blob":  
                    file_path = item["path"]
                    for pattern in file_patterns:
                        if re.search(pattern, file_path):
                            matching_files.append(file_path)
                            break

            return matching_files
        except requests.RequestException as e:
            logger.error(f"Error searching files in {repo_full_name}: {str(e)}")
            return []
        except KeyError:
            logger.error(f"Unexpected response format when searching files in {repo_full_name}")
            return []


class GitLabClient(RepositoryClient):
    """Client for interacting with the GitLab API."""

    def __init__(self, token: str, gitlab_url: str = "https://gitlab.com"):
        self.token = token
        self.base_url = f"{gitlab_url}/api/v4"
        self.session = requests.Session()
        self.session.headers.update({
            "PRIVATE-TOKEN": token
        })

    def _handle_rate_limit(self, response):
        """Handle GitLab API rate limiting."""
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            logger.warning(f"{COLOR_YELLOW}Rate limit exceeded. Sleeping for {retry_after} seconds.{COLOR_RESET}")
            time.sleep(retry_after)
            return True
        return False

    def get_repositories(self, owner: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get repositories for a specific GitLab user or group."""
        url = f"{self.base_url}/users/{owner}/projects"
        params = {"per_page": 100}
        all_repos = []

        try:
            while url and len(all_repos) < limit:
                response = self.session.get(url, params=params)

                if self._handle_rate_limit(response):
                    continue

                if response.status_code == 200:
                    repos = response.json()
                    all_repos.extend(repos)

                    if 'next' in response.links and len(all_repos) < limit:
                        url = response.links['next']['url']
                        params = {}
                    else:
                        url = None
                else:

                    url = f"{self.base_url}/groups/{owner}/projects"
                    response = self.session.get(url, params=params)

                    if self._handle_rate_limit(response):
                        continue

                    response.raise_for_status()
                    repos = response.json()
                    all_repos.extend(repos)

                    if 'next' in response.links and len(all_repos) < limit:
                        url = response.links['next']['url']
                        params = {}
                    else:
                        url = None

            return all_repos[:limit]
        except requests.RequestException as e:
            logger.error(f"Error fetching repositories for {owner}: {str(e)}")
            return []

    def search_repositories(self, language: str, min_stars: int = 0, max_stars: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Search for repositories by language and popularity with optional max stars."""
        url = f"{self.base_url}/projects"
        language_map = {
            "python": "python",
            "javascript": "javascript",
            "typescript": "typescript",
            "node": "javascript"
        }
        lang_id = language_map.get(language.lower(), language.lower())

        params = {
            "min_access_level": "public",
            "order_by": "stars_count",
            "sort": "desc",
            "per_page": 100
        }
        all_repos = []

        try:
            while url and len(all_repos) < limit:
                response = self.session.get(url, params=params)

                if self._handle_rate_limit(response):
                    continue

                response.raise_for_status()
                repos = response.json()

                filtered_repos = [
                    repo for repo in repos
                    if (repo.get("star_count", 0) >= min_stars and
                        (max_stars is None or repo.get("star_count", 0) <= max_stars) and # Added max_stars condition
                        (repo.get("tag_list", []) and lang_id in repo.get("tag_list", [])) or
                        lang_id in str(repo.get("description", "")).lower())
                ]

                all_repos.extend(filtered_repos)

                if 'next' in response.links and len(all_repos) < limit:
                    url = response.links['next']['url']
                    params = {}  
                else:
                    url = None

            return all_repos[:limit]
        except requests.RequestException as e:
            logger.error(f"Error searching repositories for language {language}: {str(e)}")
            return []

    def get_file_content(self, repo_full_name: str, file_path: str) -> str:
        """Get content of a specific file from a GitLab repository."""
        encoded_repo = repo_full_name.replace("/", "%2F")
        encoded_file_path = quote(file_path, safe='')
        url = f"{self.base_url}/projects/{encoded_repo}/repository/files/{encoded_file_path}/raw"

        try:
            response = self.session.get(url, params={"ref": "main"})

            if self._handle_rate_limit(response):
                return self.get_file_content(repo_full_name, file_path)

            if response.status_code != 200:
                response = self.session.get(url, params={"ref": "master"})

                if response.status_code != 200:
                    return ""

            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching file {file_path} from {repo_full_name}: {str(e)}")
            return ""

    def search_files(self, repo_full_name: str, file_patterns: List[str]) -> List[str]:
        """Search for files matching patterns in a GitLab repository."""
        encoded_repo = repo_full_name.replace("/", "%2F")

        branches_to_try = ["main", "master"]
        matching_files = []

        for branch in branches_to_try:
            url = f"{self.base_url}/projects/{encoded_repo}/repository/tree"
            params = {"recursive": True, "per_page": 100, "ref": branch}

            try:
                response = self.session.get(url, params=params)

                if self._handle_rate_limit(response):
                    continue

                if response.status_code != 200:
                    continue

                response.raise_for_status()

                items = response.json()
                for item in items:
                    if item["type"] == "blob":  
                        file_path = item["path"]
                        for pattern in file_patterns:
                            if re.search(pattern, file_path):
                                matching_files.append(file_path)
                                break

                if matching_files:
                    break

            except requests.RequestException as e:
                logger.error(f"Error searching files in {repo_full_name} with branch {branch}: {str(e)}")

        return matching_files


class DependencyExtractor:
    """Base class for extracting dependencies from project files."""

    def extract_dependencies(self, file_content: str) -> List[Dict[str, str]]:
        """Extract dependencies from file content."""
        raise NotImplementedError("Subclasses must implement this method")


class PythonDependencyExtractor(DependencyExtractor):
    """Extracts dependencies from Python project files."""

    def extract_from_requirements(self, content: str) -> List[Dict[str, str]]:
        """Extract dependencies from requirements.txt file."""
        dependencies = []

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            line = line.split('#')[0].strip()

            if line.startswith('-') or line.startswith('http'):
                continue

            match = re.match(r'^([a-zA-Z0-9_\-\.]+)(?:[<>=!~]+([a-zA-Z0-9_\-\.,]+))?.*$', line)
            if match:
                package_name = match.group(1)
                version = match.group(2) if match.group(2) else "latest"
                dependencies.append({"name": package_name, "version": version})

        return dependencies

    def extract_from_setup_py(self, content: str) -> List[Dict[str, str]]:
        """Extract dependencies from setup.py file."""
        dependencies = []

        install_requires_match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if install_requires_match:
            install_requires = install_requires_match.group(1)
            for package in re.finditer(r'[\'\"](.*?)[\'\"]', install_requires):
                package_str = package.group(1)
                package_match = re.match(r'^([a-zA-Z0-9_\-\.]+)(?:[<>=!~]+([a-zA-Z0-9_\-\.,]+))?.*$', package_str)
                if package_match:
                    package_name = package_match.group(1)
                    version = package_match.group(2) if package_match.group(2) else "latest"
                    dependencies.append({"name": package_name, "version": version})

        return dependencies

    def extract_from_pyproject_toml(self, content: str) -> List[Dict[str, str]]:
        """Extract dependencies from pyproject.toml file."""
        dependencies = []

        try:
            data = toml.loads(content)

            if "tool" in data and "poetry" in data["tool"] and "dependencies" in data["tool"]["poetry"]:
                for pkg, ver in data["tool"]["poetry"]["dependencies"].items():
                    if pkg != "python":
                        if isinstance(ver, str):
                            dependencies.append({"name": pkg, "version": ver})
                        else:
                            dependencies.append({"name": pkg, "version": "latest"})

            if "project" in data and "dependencies" in data["project"]:
                for dep in data["project"]["dependencies"]:
                    match = re.match(r'^([a-zA-Z0-9_\-\.]+)(?:[<>=!~]+([a-zA-Z0-9_\-\.,]+))?.*$', dep)
                    if match:
                        package_name = match.group(1)
                        version = match.group(2) if match.group(2) else "latest"
                        dependencies.append({"name": package_name, "version": version})

        except Exception as e:
            logger.error(f"Error parsing pyproject.toml: {str(e)}")

        return dependencies

    def extract_dependencies(self, file_content: str, file_path: str = "") -> List[Dict[str, str]]:
        """Extract dependencies from Python project files based on file type."""
        if file_path.endswith("requirements.txt"):
            return self.extract_from_requirements(file_content)
        elif file_path.endswith("setup.py"):
            return self.extract_from_setup_py(file_content)
        elif file_path.endswith("pyproject.toml"):
            return self.extract_from_pyproject_toml(file_content)
        else:
            if "install_requires" in file_content:
                return self.extract_from_setup_py(file_content)
            elif "[tool.poetry]" in file_content or "[project]" in file_content:
                return self.extract_from_pyproject_toml(file_content)
            else:
                return self.extract_from_requirements(file_content)


class NodeDependencyExtractor(DependencyExtractor):
    """Extracts dependencies from Node.js project files."""

    def extract_dependencies(self, file_content: str, file_path: str = "") -> List[Dict[str, str]]:
        """Extract dependencies from package.json file."""
        dependencies = []

        try:
            data = json.loads(file_content)

            if "dependencies" in data:
                for pkg, ver in data["dependencies"].items():
                    dependencies.append({"name": pkg, "version": ver})

            if "devDependencies" in data:
                for pkg, ver in data["devDependencies"].items():
                    dependencies.append({"name": pkg, "version": ver, "type": "dev"})

            if "peerDependencies" in data:
                for pkg, ver in data["peerDependencies"].items():
                    dependencies.append({"name": pkg, "version": ver, "type": "peer"})

            if "optionalDependencies" in data:
                for pkg, ver in data["optionalDependencies"].items():
                    dependencies.append({"name": pkg, "version": ver, "type": "optional"})

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing package.json: {str(e)}")

        return dependencies


class SupplyChainAnalyzer:
    """Main class to analyze repositories for supply chain vulnerabilities."""

    def __init__(self, repo_client: RepositoryClient, max_workers: int = 5):
        self.repo_client = repo_client
        self.python_extractor = PythonDependencyExtractor()
        self.node_extractor = NodeDependencyExtractor()
        self.pypi_checker = PyPIChecker()
        self.npm_checker = NPMChecker()
        self.max_workers = max_workers
        self.suspicious_packages_tui = [] 

        self.python_dependency_filenames = [
            "requirements.txt",
            "setup.py",
            "pyproject.toml",
        ]
        self.node_dependency_filenames = [
            "package.json",
        ]

    def analyze_repository(self, repo: Dict[str, Any], output_format: str = "json") -> Dict[str, Any]:
        """Analyze a repository for potential supply chain vulnerabilities."""
        repo_full_name = repo.get("full_name") or f"{repo.get('namespace', {}).get('name', 'unknown')}/{repo.get('name', 'unknown')}"
        logger.info(f"Analyzing repository: {repo_full_name}")

        result = {
            "repository": repo_full_name,
            "url": repo.get("html_url") or repo.get("web_url", ""),
            "stars": repo.get("stargazers_count") or repo.get("star_count", 0),
            "python_dependencies": [],
            "node_dependencies": [],
            "suspicious_packages": []
        }

        for file_path in self.python_dependency_filenames:
            file_content = self.repo_client.get_file_content(repo_full_name, file_path)
            if file_content:
                logger.info(f"Found Python dependency file: {file_path}")
                dependencies = self.python_extractor.extract_dependencies(file_content, file_path)
                result["python_dependencies"].extend(dependencies)

                for dep in dependencies:
                    exists = self.pypi_checker.check_dependency(dep["name"], dep.get("version"))
                    if not exists:
                        logger.warning(f"{COLOR_YELLOW}Suspicious Python package found: {COLOR_RED}{dep['name']}{COLOR_YELLOW} in {repo_full_name}{COLOR_RESET}")
                        if output_format == "tui":
                            self.suspicious_packages_tui.append({**dep, "repository": repo_full_name, "ecosystem": "PyPI"})

        for file_path in self.node_dependency_filenames:
            file_content = self.repo_client.get_file_content(repo_full_name, file_path)
            if file_content:
                logger.info(f"Found Node.js dependency file: {file_path}")
                dependencies = self.node_extractor.extract_dependencies(file_content)
                result["node_dependencies"].extend(dependencies)

                for dep in dependencies:
                    exists = self.npm_checker.check_dependency(dep["name"], dep.get("version"))
                    if not exists:
                        logger.warning(f"{COLOR_YELLOW}Suspicious Node.js package found: {COLOR_RED}{dep['name']}{COLOR_YELLOW} in {repo_full_name}{COLOR_RESET}")
                        if output_format == "tui":
                            self.suspicious_packages_tui.append({**dep, "repository": repo_full_name, "ecosystem": "npm"})

        result["suspicious_packages"].extend(self.pypi_checker.get_suspicious_packages())
        result["suspicious_packages"].extend(self.npm_checker.get_suspicious_packages())

        self.pypi_checker.suspicious_packages = []
        self.npm_checker.suspicious_packages = []

        return result

    def analyze_owner(self, owner: str, limit: int = 10, output_format: str = "json") -> List[Dict[str, Any]]:
        """Analyze all repositories for a specific owner."""
        logger.info(f"Analyzing repositories for owner: {owner}")

        repositories = self.repo_client.get_repositories(owner, limit)
        return self._process_repositories(repositories, output_format)

    def analyze_language(self, language: str, min_stars: int = 0, max_stars: Optional[int] = None, limit: int = 100, output_format: str = "json") -> List[Dict[str, Any]]:
        """Analyze popular repositories for a specific language."""
        logger.info(f"Analyzing popular {language} repositories with stars between {min_stars} and {max_stars}")

        repositories = self.repo_client.search_repositories(language, min_stars, max_stars, limit)
        return self._process_repositories(repositories, output_format)

    def _process_repositories(self, repositories: List[Dict[str, Any]], output_format: str = "json") -> List[Dict[str, Any]]:
        """Process multiple repositories with parallel execution."""
        results = []
        self.suspicious_packages_tui = []
        if not repositories:
            logger.warning(f"{COLOR_YELLOW}No repositories found to analyze.{COLOR_RESET}")
            return results

        logger.info(f"Found {len(repositories)} repositories to analyze")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_repo = {executor.submit(self.analyze_repository, repo, output_format): repo for repo in repositories}

            for future in concurrent.futures.as_completed(future_to_repo):
                repo = future_to_repo[future]
                repo_name = repo.get("full_name") or repo.get("name", "unknown")

                try:
                    result = future.result()
                    results.append(result)
                    suspicious_count = len(result["suspicious_packages"])

                    if suspicious_count > 0:
                        logger.warning(f"{COLOR_YELLOW}Repository {repo_name} has {COLOR_RED}{suspicious_count}{COLOR_YELLOW} suspicious packages{COLOR_RESET}")
                    else:
                        logger.info(f"Repository {repo_name} analysis complete. No suspicious packages found.")

                except Exception as e:
                    logger.error(f"{COLOR_RED}Error analyzing repository {repo_name}: {str(e)}{COLOR_RESET}")

        if output_format == "tui" and self.suspicious_packages_tui:
            display_tui_output(self.suspicious_packages_tui)

        return results


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Supply Chain Security Mass Scanner")

    auth_group = parser.add_mutually_exclusive_group(required=True) # Require either github or gitlab token
    auth_group.add_argument("--github-token", help="GitHub API token", default=os.environ.get("GITHUB_TOKEN"))
    auth_group.add_argument("--gitlab-token", help="GitLab API token", default=os.environ.get("GITLAB_TOKEN"))

    analysis_mode_group = parser.add_mutually_exclusive_group(required=True)
    analysis_mode_group.add_argument("--owner", help="GitHub/GitLab owner to analyze repositories for")
    analysis_mode_group.add_argument("--language", help="Language to search popular repositories for")

    parser.add_argument("--gitlab-url", help="GitLab instance URL (for self-hosted GitLab)", default="https://gitlab.com")
    parser.add_argument("--min-stars", type=int, default=0, help="Minimum stars for language-based search")
    parser.add_argument("--max-stars", type=int, default=None, help="Maximum stars for language-based search") # Added max-stars argument
    parser.add_argument("--limit", type=int, default=10, help="Limit number of repositories to analyze")
    parser.add_argument("--max-workers", type=int, default=5, help="Maximum concurrent workers for repository analysis")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level"
    )
    parser.add_argument(
        "--output-format",
        default="json",
        choices=["json", "text", "tui"],
        help="Output format for results (json, text, tui)"
    )

    args = parser.parse_args()
    return args

def format_text_output(results: List[Dict[str, Any]]) -> str:
    """Format analysis results into a human-readable text report with colors."""
    report = ""
    for repo_result in results:
        report += f"{COLOR_CYAN}Repository: {repo_result['repository']}{COLOR_RESET}\n"
        report += f"URL: {repo_result['url']}\n"
        report += f"Stars: {repo_result['stars']}\n"

        if repo_result["suspicious_packages"]:
            report += f"  {COLOR_RED}Suspicious Packages:{COLOR_RESET}\n"
            for package in repo_result["suspicious_packages"]:
                report += f"    - Name: {COLOR_RED}{package['name']}{COLOR_RESET}, Version: {package['version']}, Issue: {package['issue']}, Risk: {package['risk']}\n"
        else:
            report += f"  {COLOR_GREEN}No suspicious packages found.{COLOR_RESET}\n"
        report += "\n"
    return report

def display_tui_output(suspicious_packages: List[Dict[str, Any]]):
    """Display suspicious packages in a simple TUI in the terminal."""
    if not suspicious_packages:
        print(f"{COLOR_GREEN}No suspicious packages found during analysis.{COLOR_RESET}")
        return

    print(f"\n{COLOR_RED}{'='*50} SUSPICIOUS PACKAGES DETECTED {'='*50}{COLOR_RESET}\n")
    for package in suspicious_packages:
        print(f"{COLOR_MAGENTA}Repository:{COLOR_RESET} {package['repository']}")
        print(f"  {COLOR_MAGENTA}Ecosystem:{COLOR_RESET} {package['ecosystem']}")
        print(f"  {COLOR_RED}Package Name:{COLOR_RESET} {COLOR_RED}{package['name']}{COLOR_RESET}")
        print(f"  {COLOR_BLUE}Version:{COLOR_RESET} {package['version']}")
        print(f"  {COLOR_YELLOW}Issue:{COLOR_RESET} {package['issue']}")
        print(f"  {COLOR_YELLOW}Risk:{COLOR_RESET} {package['risk']}")
        print("-" * 100)
    print(f"\n{COLOR_RED}{'='*113}{COLOR_RESET}\n")


if __name__ == "__main__":
    args = parse_arguments()

    logger.setLevel(args.log_level.upper())

    client = None
    if args.github_token:
        logger.info("Using GitHub client")
        client = GitHubClient(token=args.github_token)
    elif args.gitlab_token:
        logger.info("Using GitLab client")
        client = GitLabClient(token=args.gitlab_token, gitlab_url=args.gitlab_url)
    else:
        logger.error(f"{COLOR_RED}Either --github-token or --gitlab-token must be provided.{COLOR_RESET}")
        sys.exit(1)

    analyzer = SupplyChainAnalyzer(repo_client=client, max_workers=args.max_workers)
    results = []

    if args.owner:
        logger.info(f"Analyzing owner: {args.owner} repositories, limit={args.limit}")
        results = analyzer.analyze_owner(args.owner, limit=args.limit, output_format=args.output_format)
    elif args.language:
        logger.info(f"Analyzing language: {args.language} repositories, min_stars={args.min_stars}, max_stars={args.max_stars}, limit={args.limit}")
        results = analyzer.analyze_language(args.language, args.min_stars, args.max_stars, limit=args.limit, output_format=args.output_format)
    else:
        logger.error(f"{COLOR_RED}Analysis mode (--owner or --language) must be specified.{COLOR_RESET}")
        sys.exit(1)

    if args.output_format == "json":
        print(json.dumps(results, indent=2))
    elif args.output_format == "text":
        print(format_text_output(results))
    elif args.output_format == "tui":
        if args.output_format != "tui" or not analyzer.suspicious_packages_tui:
            print(format_text_output(results)) 
