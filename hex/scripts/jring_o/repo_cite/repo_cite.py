import requests
import json
import csv
import time
import re
import base64
import logging
import os
import argparse
import uuid
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from tqdm import tqdm
import urllib.parse

# Logging Handler to work with tqdm
class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        
    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Configure logging to use the custom handler
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[TqdmLoggingHandler()]
)

# Constants
GITHUB_API_URL = "https://api.github.com"
OPENALEX_API_URL = "https://api.openalex.org"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

def github_api_request(url, headers, params=None):
    """
    Sends a GET request to the GitHub API with rate limit handling.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        logging.debug(f"Attempt {attempt} for URL: {url}")
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            logging.error(f"Timeout occurred for URL: {url}")
            if attempt == MAX_RETRIES:
                raise
            else:
                time.sleep(RETRY_DELAY)
                continue
        except requests.exceptions.RequestException as e:
            logging.error(f"Request exception: {e}")
            if attempt == MAX_RETRIES:
                raise
            else:
                time.sleep(RETRY_DELAY)
                continue

        logging.debug(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            logging.debug("Successful response.")
            return response.json(), response.headers
        elif response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
            if response.headers['X-RateLimit-Remaining'] == '0':
                reset_time = int(response.headers['X-RateLimit-Reset'])
                sleep_time = max(reset_time - int(time.time()), 0) + 1
                logging.warning(
                    f"Rate limit exceeded. Sleeping for {sleep_time} seconds."
                )
                time.sleep(sleep_time)
                continue
        else:
            logging.error(f"Error: {response.status_code} - {response.reason}")
            if attempt == MAX_RETRIES:
                response.raise_for_status()
            else:
                time.sleep(RETRY_DELAY)
                continue
    raise Exception(
        f"Failed to get a successful response after {MAX_RETRIES} attempts."
    )

def get_next_link(headers):
    """
    Parses the 'Link' header from GitHub API response to find the next page URL.
    """
    link_header = headers.get('Link', '')
    if not link_header:
        return None
    links = link_header.split(',')
    for link in links:
        parts = link.split(';')
        if len(parts) < 2:
            continue
        url_part = parts[0].strip()
        rel_part = parts[1].strip()
        if rel_part == 'rel="next"':
            next_url = url_part.lstrip('<').rstrip('>')
            return next_url
    return None

def search_repositories_with_queries(query_terms, headers):
    """
    Searches GitHub repositories based on query terms and records matching queries.
    """
    repositories = {}
    for query_term in query_terms:
        params = {'q': query_term, 'per_page': 100}
        url = f"{GITHUB_API_URL}/search/repositories"
        while url:
            logging.debug(
                f"Searching repositories with URL: {url} and params: {params}"
            )
            try:
                data, headers_response = github_api_request(url, headers, params)
            except Exception as e:
                logging.error(f"Error searching repositories: {e}")
                break
            if data:
                items = data.get('items', [])
                logging.info(
                    f"Found {len(items)} repositories in this page for query '{query_term}'."
                )
                for repo in items:
                    repo_id = repo.get('id')
                    if repo_id in repositories:
                        repositories[repo_id]['queries'].add(query_term)
                    else:
                        repositories[repo_id] = {
                            'repo_data': repo,
                            'queries': set([query_term])
                        }
                next_url = get_next_link(headers_response)
                url = next_url
                params = None  # Parameters are only needed for the initial request
            else:
                break
    return repositories

def extract_doi_from_repo(owner, repo_name, headers):
    """
    Attempts to extract the DOI of the associated paper from the repository.
    """
    # Try to get README content
    readme_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/readme"
    try:
        readme_data, _ = github_api_request(readme_url, headers)
        if readme_data and 'content' in readme_data:
            readme_content = base64.b64decode(readme_data['content']).decode('utf-8', errors='ignore')
            doi_match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', readme_content, re.I)
            if doi_match:
                doi = doi_match.group(1)
                logging.info(f"DOI found in README: {doi}")
                return doi
    except Exception as e:
        logging.warning(f"Could not retrieve README for {owner}/{repo_name}: {e}")
    # List repository contents to find CITATION.cff with any capitalization
    contents_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/contents"
    try:
        contents, _ = github_api_request(contents_url, headers)
        if contents and isinstance(contents, list):
            for content in contents:
                if content['name'].lower() == 'citation.cff':
                    citation_url = content['url']
                    try:
                        citation_data, _ = github_api_request(citation_url, headers)
                        if citation_data and 'content' in citation_data:
                            citation_content = base64.b64decode(citation_data['content']).decode('utf-8', errors='ignore')
                            doi_match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', citation_content, re.I)
                            if doi_match:
                                doi = doi_match.group(1)
                                logging.info(f"DOI found in CITATION.cff: {doi}")
                                return doi
                    except Exception as e:
                        logging.warning(f"Could not retrieve {content['name']} for {owner}/{repo_name}: {e}")
    except Exception as e:
        logging.warning(f"Could not retrieve contents for {owner}/{repo_name}: {e}")
    # Try to get repository description
    repo_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}"
    try:
        repo_data, _ = github_api_request(repo_url, headers)
        description = repo_data.get('description', '')
        doi_match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', description, re.I)
        if doi_match:
            doi = doi_match.group(1)
            logging.info(f"DOI found in repository description: {doi}")
            return doi
    except Exception as e:
        logging.warning(f"Could not retrieve repository data for {owner}/{repo_name}: {e}")
    logging.info(f"No DOI found for repository {owner}/{repo_name}")
    return None

def get_paper_details_from_openalex(doi):
    """
    Fetches paper details from OpenAlex using the DOI.
    """
    doi_formatted = doi.lower()
    if not doi_formatted.startswith('10.'):
        logging.warning(f"Invalid DOI format: {doi}")
        return None
    url = f"{OPENALEX_API_URL}/works/doi:{doi_formatted}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        paper_data = response.json()
        logging.info(f"Paper details retrieved from OpenAlex for DOI: {doi}")
        # Extract domains (concepts with level 0)
        concepts = paper_data.get('concepts', [])
        domains = [concept['display_name'] for concept in concepts if concept.get('level') == 0]
        paper_data['domains'] = domains
        return paper_data
    except requests.RequestException as e:
        logging.error(f"Error fetching paper details from OpenAlex: {e}")
    return None

def get_authors_and_institutions(paper_data):
    """
    Extracts authors' information including names, ORCID, institutions, author IDs, and initializes other_papers list.
    """
    authors_info = []
    authorships = paper_data.get('authorships', [])
    for authorship in authorships:
        author = authorship.get('author', {})
        institutions = authorship.get('institutions', [])
        author_name = author.get('display_name')
        orcid = author.get('orcid')
        institution_names = [inst.get('display_name') for inst in institutions]
        authors_info.append({
            'author_name': author_name,
            'orcid': orcid,
            'institutions': institution_names,
            'author_id': author.get('id'),
            'other_papers': []  # Initialize an empty list for other papers
        })
    return authors_info

def get_other_papers_by_authors(authors_info, doi):
    """
    Retrieves other papers for each author and updates the authors_info list.
    """
    for author in authors_info:
        author_id = author.get('author_id')
        author_name = author.get('author_name')
        if author_id:
            url = f"{OPENALEX_API_URL}/works"
            params = {
                'filter': f'authorships.author.id:{author_id}',
                'per-page': 200,
                'page': 1,
                'cursor': '*'
            }
            all_papers = []
            while True:
                try:
                    response = requests.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    papers = data.get('results', [])
                    for paper in papers:
                        # Exclude the paper being analyzed
                        paper_doi = paper.get('doi') or ''
                        if paper_doi.lower() != doi.lower():
                            paper_info = {
                                'title': paper.get('title'),
                                'publication_year': paper.get('publication_year'),
                                'doi': paper_doi,
                                'concepts': [concept['display_name'] for concept in paper.get('concepts', [])]
                            }
                            all_papers.append(paper_info)
                    if 'next_cursor' in data.get('meta', {}) and data['meta']['next_cursor']:
                        params['cursor'] = data['meta']['next_cursor']
                    else:
                        break
                except requests.RequestException as e:
                    logging.error(f"Error fetching works for author {author_name}: {e}")
                    break
            author['other_papers'] = all_papers
            logging.info(f"Retrieved {len(all_papers)} other papers for author: {author_name}")
    return authors_info  # Return updated authors_info

def get_first_degree_citations(paper_data):
    """
    Retrieves first-degree citations (papers citing the paper being analyzed).
    """
    first_degree_citations = []
    cited_by_count = paper_data.get('cited_by_count', 0)
    if cited_by_count > 0:
        cited_by_api_url = paper_data.get('cited_by_api_url')
        cursor = '*'
        while True:
            params = {'per-page': 200, 'cursor': cursor}
            try:
                response = requests.get(cited_by_api_url, params=params)
                response.raise_for_status()
                data = response.json()
                papers = data.get('results', [])
                for paper in papers:
                    paper_info = {
                        'title': paper.get('title'),
                        'authors': [auth['author']['display_name'] for auth in paper.get('authorships', [])],
                        'publication_year': paper.get('publication_year'),
                        'doi': paper.get('doi'),
                        'concepts': [concept['display_name'] for concept in paper.get('concepts', [])],
                        'cited_by_count': paper.get('cited_by_count', 0),
                        'cited_by_api_url': paper.get('cited_by_api_url', '')
                    }
                    first_degree_citations.append(paper_info)
                if data.get('meta', {}).get('next_cursor'):
                    cursor = data['meta']['next_cursor']
                else:
                    break
            except requests.RequestException as e:
                logging.error(f"Error fetching first-degree citations: {e}")
                break
    else:
        logging.info("No first-degree citations found.")
    logging.info(f"{len(first_degree_citations)} first-degree citations retrieved.")
    return first_degree_citations

def get_second_degree_citations(first_degree_citations):
    """
    Retrieves second-degree citations and maps them to the first-degree papers they cite.
    """
    second_degree_citations = []
    for first_degree_paper in first_degree_citations:
        first_paper_title = first_degree_paper.get('title')
        first_paper_doi = first_degree_paper.get('doi')
        cited_by_count = first_degree_paper.get('cited_by_count', 0)
        cited_by_api_url = first_degree_paper.get('cited_by_api_url', '')
        if cited_by_count > 0 and cited_by_api_url:
            cursor = '*'
            while True:
                params = {'per-page': 200, 'cursor': cursor}
                try:
                    response = requests.get(cited_by_api_url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    papers = data.get('results', [])
                    for second_paper in papers:
                        paper_info = {
                            'title': second_paper.get('title'),
                            'authors': [auth['author']['display_name'] for auth in second_paper.get('authorships', [])],
                            'publication_year': second_paper.get('publication_year'),
                            'doi': second_paper.get('doi'),
                            'concepts': [concept['display_name'] for concept in second_paper.get('concepts', [])],
                            'cited_by_count': second_paper.get('cited_by_count', 0),
                            'cited_by_api_url': second_paper.get('cited_by_api_url', ''),
                            'cites_first_degree_paper': {
                                'title': first_paper_title,
                                'doi': first_paper_doi
                            }
                        }
                        second_degree_citations.append(paper_info)
                    if data.get('meta', {}).get('next_cursor'):
                        cursor = data['meta']['next_cursor']
                    else:
                        break
                except requests.RequestException as e:
                    logging.error(f"Error fetching second-degree citations: {e}")
                    break
    logging.info(f"{len(second_degree_citations)} second-degree citations retrieved.")
    return second_degree_citations

def get_contributors_and_participants(owner, repo_name, headers):
    # Get contributors
    contributors_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/contributors"
    contributors = []
    try:
        contributors_data, _ = github_api_request(contributors_url, headers)
        contributors.extend(contributors_data)
        logging.info(f"{len(contributors)} contributors retrieved.")
    except Exception as e:
        logging.error(f"Error fetching contributors: {e}")

    # Get participants from issues and comments
    issues_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/issues"
    participants = set()
    page = 1
    per_page = 100
    while True:
        params = {'state': 'all', 'per_page': per_page, 'page': page}
        try:
            issues_data, headers_response = github_api_request(issues_url, headers, params=params)
            if not issues_data:
                break
            for issue in issues_data:
                user = issue.get('user', {})
                if user:
                    participants.add(user.get('login'))
                # Get comments for the issue
                comments_url = issue.get('comments_url')
                comments_page = 1
                while True:
                    comments_params = {'per_page': per_page, 'page': comments_page}
                    try:
                        comments_data, _ = github_api_request(comments_url, headers, params=comments_params)
                        if not comments_data:
                            break
                        for comment in comments_data:
                            commenter = comment.get('user', {})
                            if commenter:
                                participants.add(commenter.get('login'))
                        if len(comments_data) < per_page:
                            break
                        comments_page += 1
                    except Exception as e:
                        logging.error(f"Error fetching comments: {e}")
                        break
            if 'next' in headers_response.get('Link', ''):
                page += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching issues: {e}")
            break
    logging.info(f"{len(participants)} participants retrieved from issues and comments.")
    return contributors, participants

def get_contributor_details(contributors, headers):
    """
    Fetches real names of contributors from their GitHub profiles.
    """
    contributor_details = []
    for contributor in contributors:
        username = contributor.get('login')
        user_url = f"{GITHUB_API_URL}/users/{username}"
        try:
            user_data, _ = github_api_request(user_url, headers)
            real_name = user_data.get('name')
            contributor_details.append({
                'username': username,
                'real_name': real_name
            })
        except Exception as e:
            logging.error(f"Error fetching user data for {username}: {e}")
            contributor_details.append({
                'username': username,
                'real_name': None
            })
    return contributor_details

def analyze_connections(contributors, participants, authors_info):
    """
    Analyze how contributors and participants connect with the authors.
    """
    connections = []
    author_names = {author['author_name'].lower() for author in authors_info}
    # Analyze contributors
    for contributor in contributors:
        login = contributor.get('login', '').lower()
        name = contributor.get('name', '').lower() if contributor.get('name') else ''
        if login in author_names or name in author_names:
            connections.append({'username': contributor.get('login'), 'role': 'Contributor', 'connection': 'Author'})
    # Analyze participants
    for participant in participants:
        participant_lower = participant.lower()
        if participant_lower in author_names:
            connections.append({'username': participant, 'role': 'Participant', 'connection': 'Author'})
    logging.info(f"{len(connections)} connections found between contributors/participants and authors.")
    return connections

def analyze_contributor_affiliations(contributors, headers):
    """
    Analyzes contributors to determine their affiliations.
    """
    affiliations = []
    for contributor in contributors:
        username = contributor.get('login')
        user_url = f"{GITHUB_API_URL}/users/{username}"
        try:
            user_data, _ = github_api_request(user_url, headers)
            company = user_data.get('company')
            email = user_data.get('email')
            # Use company field as affiliation
            affiliation = company.strip() if company else None
            # Alternatively, use email domain to infer affiliation
            if not affiliation and email:
                email_domain = email.split('@')[-1]
                affiliation = email_domain
            affiliations.append({
                'username': username,
                'affiliation': affiliation
            })
        except Exception as e:
            logging.error(f"Error fetching user data for {username}: {e}")
            affiliations.append({
                'username': username,
                'affiliation': None
            })
    return affiliations

def classify_contributor_roles(contributors):
    """
    Classifies contributors into roles based on their activity.
    """
    # Fetch total number of commits per contributor
    contributor_commits = []
    for contributor in contributors:
        username = contributor.get('login')
        commits = contributor.get('contributions', 0)
        contributor_commits.append((username, commits))
    
    # Sort contributors by number of commits in descending order
    contributor_commits.sort(key=lambda x: x[1], reverse=True)
    total_contributors = len(contributor_commits)
    roles = {}
    for idx, (username, commits) in enumerate(contributor_commits):
        percentile = (idx + 1) / total_contributors
        if percentile <= 0.10:
            role = 'Core Contributor'
        elif percentile <= 0.50:
            role = 'Occasional Contributor'
        else:
            role = 'One-time Contributor'
        roles[username] = {
            'commits': commits,
            'role': role
        }
    return roles

def get_total_issues(owner, repo_name, headers):
    """
    Retrieves the total number of issues, open issues, and closed issues.
    """
    url = f"{GITHUB_API_URL}/search/issues"
    query = f"repo:{owner}/{repo_name} is:issue"
    params = {'q': query, 'per_page': 1}
    total_issues = open_issues = closed_issues = None
    try:
        data, _ = github_api_request(url, headers, params)
        total_issues = data.get('total_count', 0)
    except Exception as e:
        logging.error(f"Error fetching total issues for {owner}/{repo_name}: {e}")
    # Open issues
    params['q'] = query + ' is:open'
    try:
        data, _ = github_api_request(url, headers, params)
        open_issues = data.get('total_count', 0)
    except Exception as e:
        logging.error(f"Error fetching open issues for {owner}/{repo_name}: {e}")
    # Closed issues
    params['q'] = query + ' is:closed'
    try:
        data, _ = github_api_request(url, headers, params)
        closed_issues = data.get('total_count', 0)
    except Exception as e:
        logging.error(f"Error fetching closed issues for {owner}/{repo_name}: {e}")
    return total_issues, open_issues, closed_issues

def get_average_issue_close_time(owner, repo_name, headers):
    """
    Calculates the average time to close issues.
    """
    issues_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/issues"
    params = {'state': 'closed', 'per_page': 100, 'page': 1}
    total_time = 0
    issue_count = 0
    while True:
        try:
            issues_data, headers_response = github_api_request(issues_url, headers, params=params)
            if not issues_data:
                break
            for issue in issues_data:
                if 'pull_request' in issue:
                    continue  # Skip pull requests
                created_at = issue.get('created_at')
                closed_at = issue.get('closed_at')
                if created_at and closed_at:
                    created_time = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
                    closed_time = datetime.strptime(closed_at, '%Y-%m-%dT%H:%M:%SZ')
                    time_to_close = (closed_time - created_time).total_seconds()
                    total_time += time_to_close
                    issue_count += 1
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching closed issues for average close time: {e}")
            break
    if issue_count > 0:
        average_time = total_time / issue_count
        average_time_days = average_time / (60 * 60 * 24)  # Convert seconds to days
    else:
        average_time_days = None
    return average_time_days

def get_issue_update_frequency(owner, repo_name, headers, days=30):
    """
    Calculates the number of issues updated in the last 'days' days.
    """
    since_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
    issues_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/issues"
    params = {'since': since_date, 'per_page': 100, 'page': 1, 'state': 'all'}
    update_count = 0
    while True:
        try:
            issues_data, headers_response = github_api_request(issues_url, headers, params=params)
            if not issues_data:
                break
            update_count += len(issues_data)
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching issue updates: {e}")
            break
    return update_count

def get_total_prs(owner, repo_name, headers):
    """
    Retrieves the total number of PRs, open PRs, and closed PRs.
    """
    url = f"{GITHUB_API_URL}/search/issues"
    query = f"repo:{owner}/{repo_name} is:pr"
    params = {'q': query, 'per_page': 1}
    total_prs = open_prs = closed_prs = None
    try:
        data, _ = github_api_request(url, headers, params)
        total_prs = data.get('total_count', 0)
    except Exception as e:
        logging.error(f"Error fetching total PRs for {owner}/{repo_name}: {e}")
    # Open PRs
    params['q'] = query + ' is:open'
    try:
        data, _ = github_api_request(url, headers, params)
        open_prs = data.get('total_count', 0)
    except Exception as e:
        logging.error(f"Error fetching open PRs for {owner}/{repo_name}: {e}")
    # Closed PRs
    params['q'] = query + ' is:closed'
    try:
        data, _ = github_api_request(url, headers, params)
        closed_prs = data.get('total_count', 0)
    except Exception as e:
        logging.error(f"Error fetching closed PRs for {owner}/{repo_name}: {e}")
    return total_prs, open_prs, closed_prs

def get_average_pr_merge_time(owner, repo_name, headers):
    """
    Calculates the average time to merge pull requests.
    """
    prs_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/pulls"
    params = {'state': 'closed', 'per_page': 100, 'page': 1}
    total_time = 0
    pr_count = 0
    while True:
        try:
            prs_data, headers_response = github_api_request(prs_url, headers, params=params)
            if not prs_data:
                break
            for pr in prs_data:
                if pr.get('merged_at'):
                    created_at = pr.get('created_at')
                    merged_at = pr.get('merged_at')
                    if created_at and merged_at:
                        created_time = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
                        merged_time = datetime.strptime(merged_at, '%Y-%m-%dT%H:%M:%SZ')
                        time_to_merge = (merged_time - created_time).total_seconds()
                        total_time += time_to_merge
                        pr_count += 1
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching closed PRs for average merge time: {e}")
            break
    if pr_count > 0:
        average_time = total_time / pr_count
        average_time_days = average_time / (60 * 60 * 24)  # Convert seconds to days
    else:
        average_time_days = None
    return average_time_days

def get_pr_update_frequency(owner, repo_name, headers, days=30):
    """
    Calculates the number of PRs updated in the last 'days' days.
    """
    since_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
    prs_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/pulls"
    params = {'since': since_date, 'per_page': 100, 'page': 1, 'state': 'all'}
    update_count = 0
    while True:
        try:
            prs_data, headers_response = github_api_request(prs_url, headers, params=params)
            if not prs_data:
                break
            update_count += len(prs_data)
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching PR updates: {e}")
            break
    return update_count

def get_total_downloads(owner, repo_name, headers):
    """
    Retrieves the total number of downloads from releases.
    """
    releases_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/releases"
    params = {'per_page': 100, 'page': 1}
    total_downloads = 0
    recent_downloads = 0
    recent_releases_count = 0
    while True:
        try:
            releases_data, headers_response = github_api_request(releases_url, headers, params=params)
            if not releases_data:
                break
            for release in releases_data:
                assets = release.get('assets', [])
                for asset in assets:
                    download_count = asset.get('download_count', 0)
                    total_downloads += download_count
                    # Check if the release is recent (last 30 days)
                    published_at = release.get('published_at')
                    if published_at:
                        published_time = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ')
                        if published_time >= datetime.utcnow() - timedelta(days=30):
                            recent_downloads += download_count
                            recent_releases_count += 1
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching releases: {e}")
            break
    return total_downloads, recent_downloads, recent_releases_count

def get_discussion_activity_count(owner, repo_name, headers, days=30):
    """
    Retrieves the number of discussions and comments in the last 'days' days.
    """
    discussions_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/discussions"
    params = {'per_page': 100, 'page': 1}
    activity_count = 0
    while True:
        try:
            discussions_data, headers_response = github_api_request(discussions_url, headers, params=params)
            if not discussions_data:
                break
            for discussion in discussions_data:
                created_at = discussion.get('created_at')
                if created_at:
                    created_time = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
                    if created_time >= datetime.utcnow() - timedelta(days=days):
                        activity_count += 1
                # Get comments
                comments_url = discussion.get('comments_url')
                comments_params = {'per_page': 100, 'page': 1}
                while True:
                    comments_data, _ = github_api_request(comments_url, headers, params=comments_params)
                    if not comments_data:
                        break
                    for comment in comments_data:
                        comment_created_at = comment.get('created_at')
                        if comment_created_at:
                            comment_time = datetime.strptime(comment_created_at, '%Y-%m-%dT%H:%M:%SZ')
                            if comment_time >= datetime.utcnow() - timedelta(days=days):
                                activity_count += 1
                    if 'next' in headers_response.get('Link', ''):
                        comments_params['page'] += 1
                    else:
                        break
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching discussions: {e}")
            break
    return activity_count

def get_stars_forks_growth(owner, repo_name, headers):
    """
    Estimates stars and forks growth over the repository's lifetime.
    """
    repo_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}"
    try:
        repo_data, _ = github_api_request(repo_url, headers)
        created_at = repo_data.get('created_at')
        stars_count = repo_data.get('stargazers_count', 0)
        forks_count = repo_data.get('forks_count', 0)
        if created_at:
            created_time = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
            days_since_creation = (datetime.utcnow() - created_time).days
            if days_since_creation > 0:
                stars_growth = stars_count / days_since_creation
                forks_growth = forks_count / days_since_creation
            else:
                stars_growth = stars_count
                forks_growth = forks_count
        else:
            stars_growth = forks_growth = None
    except Exception as e:
        logging.error(f"Error fetching repository data for growth calculation: {e}")
        stars_growth = forks_growth = None
    return stars_growth, forks_growth

def calculate_activity_score(repo_data):
    """
    Calculates an activity score based on various metrics.
    """
    score = 0
    score += repo_data.get('recent_commits_count', 0) * 1
    score += repo_data.get('recent_issues_opened_count', 0) * 0.5
    score += repo_data.get('recent_issues_closed_count', 0) * 0.5
    score += repo_data.get('recent_prs_opened_count', 0) * 1
    score += repo_data.get('recent_prs_merged_count', 0) * 1
    score += repo_data.get('discussion_activity_count', 0) * 0.5
    return score

def get_active_contributors_count(owner, repo_name, headers, days=30):
    """
    Returns the number of unique contributors who have made commits in the last 'days' days.
    """
    since_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
    commits_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/commits"
    params = {'since': since_date, 'per_page': 100, 'page': 1}
    contributors = set()
    while True:
        try:
            commits_data, headers_response = github_api_request(commits_url, headers, params=params)
            if not commits_data:
                break
            for commit in commits_data:
                author = commit.get('author')
                if author and author.get('login'):
                    contributors.add(author['login'])
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching commits for active contributors: {e}")
            break
    return len(contributors)

def get_recent_commits_count(owner, repo_name, headers, days=30):
    """
    Returns the number of commits made in the last 'days' days.
    """
    since_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
    commits_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/commits"
    params = {'since': since_date, 'per_page': 100, 'page': 1}
    commit_count = 0
    while True:
        try:
            commits_data, headers_response = github_api_request(commits_url, headers, params=params)
            if not commits_data:
                break
            commit_count += len(commits_data)
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching recent commits: {e}")
            break
    return commit_count

def get_recent_issues_counts(owner, repo_name, headers, days=30):
    """
    Returns the number of issues opened and closed in the last 'days' days.
    """
    since_date = datetime.utcnow() - timedelta(days=days)
    issues_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/issues"
    params = {'state': 'all', 'per_page': 100, 'page': 1}
    opened_count = 0
    closed_count = 0
    while True:
        try:
            issues_data, headers_response = github_api_request(issues_url, headers, params=params)
            if not issues_data:
                break
            for issue in issues_data:
                if 'pull_request' in issue:
                    continue  # Skip pull requests
                created_at_str = issue.get('created_at')
                if created_at_str:
                    created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ')
                    if created_at >= since_date:
                        opened_count += 1
                if issue.get('state') == 'closed':
                    closed_at_str = issue.get('closed_at')
                    if closed_at_str:
                        closed_at = datetime.strptime(closed_at_str, '%Y-%m-%dT%H:%M:%SZ')
                        if closed_at >= since_date:
                            closed_count += 1
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching recent issues: {e}")
            break
    return opened_count, closed_count

def get_recent_prs_counts(owner, repo_name, headers, days=30):
    """
    Returns the number of PRs opened and merged in the last 'days' days.
    """
    since_date = datetime.utcnow() - timedelta(days=days)
    prs_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/pulls"
    params = {'state': 'all', 'per_page': 100, 'page': 1}
    opened_count = 0
    merged_count = 0
    while True:
        try:
            prs_data, headers_response = github_api_request(prs_url, headers, params=params)
            if not prs_data:
                break
            for pr in prs_data:
                created_at_str = pr.get('created_at')
                if created_at_str:
                    created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ')
                    if created_at >= since_date:
                        opened_count += 1
                merged_at_str = pr.get('merged_at')
                if merged_at_str:
                    merged_at = datetime.strptime(merged_at_str, '%Y-%m-%dT%H:%M:%SZ')
                    if merged_at >= since_date:
                        merged_count += 1
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching recent PRs: {e}")
            break
    return opened_count, merged_count

def get_active_contributors_count(owner, repo_name, headers, days=30):
    """
    Returns the number of unique contributors who have made commits in the last 'days' days.
    """
    since_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
    commits_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/commits"
    params = {'since': since_date, 'per_page': 100, 'page': 1}
    contributors = set()
    while True:
        try:
            commits_data, headers_response = github_api_request(commits_url, headers, params=params)
            if not commits_data:
                break
            for commit in commits_data:
                author = commit.get('author')
                if author and author.get('login'):
                    contributors.add(author['login'])
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching commits for active contributors: {e}")
            break
    return len(contributors)

def get_recent_commits_count(owner, repo_name, headers, days=30):
    """
    Returns the number of commits made in the last 'days' days.
    """
    since_date = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
    commits_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/commits"
    params = {'since': since_date, 'per_page': 100, 'page': 1}
    commit_count = 0
    while True:
        try:
            commits_data, headers_response = github_api_request(commits_url, headers, params=params)
            if not commits_data:
                break
            commit_count += len(commits_data)
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching recent commits: {e}")
            break
    return commit_count

def get_recent_issues_counts(owner, repo_name, headers, days=30):
    """
    Returns the number of issues opened and closed in the last 'days' days.
    """
    since_date = datetime.utcnow() - timedelta(days=days)
    issues_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/issues"
    params = {'state': 'all', 'per_page': 100, 'page': 1}
    opened_count = 0
    closed_count = 0
    while True:
        try:
            issues_data, headers_response = github_api_request(issues_url, headers, params=params)
            if not issues_data:
                break
            for issue in issues_data:
                if 'pull_request' in issue:
                    continue  # Skip pull requests
                created_at_str = issue.get('created_at')
                if created_at_str:
                    created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ')
                    if created_at >= since_date:
                        opened_count += 1
                if issue.get('state') == 'closed':
                    closed_at_str = issue.get('closed_at')
                    if closed_at_str:
                        closed_at = datetime.strptime(closed_at_str, '%Y-%m-%dT%H:%M:%SZ')
                        if closed_at >= since_date:
                            closed_count += 1
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching recent issues: {e}")
            break
    return opened_count, closed_count

def get_recent_prs_counts(owner, repo_name, headers, days=30):
    """
    Returns the number of PRs opened and merged in the last 'days' days.
    """
    since_date = datetime.utcnow() - timedelta(days=days)
    prs_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/pulls"
    params = {'state': 'all', 'per_page': 100, 'page': 1}
    opened_count = 0
    merged_count = 0
    while True:
        try:
            prs_data, headers_response = github_api_request(prs_url, headers, params=params)
            if not prs_data:
                break
            for pr in prs_data:
                created_at_str = pr.get('created_at')
                if created_at_str:
                    created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%SZ')
                    if created_at >= since_date:
                        opened_count += 1
                merged_at_str = pr.get('merged_at')
                if merged_at_str:
                    merged_at = datetime.strptime(merged_at_str, '%Y-%m-%dT%H:%M:%SZ')
                    if merged_at >= since_date:
                        merged_count += 1
            if 'next' in headers_response.get('Link', ''):
                params['page'] += 1
            else:
                break
        except Exception as e:
            logging.error(f"Error fetching recent PRs: {e}")
            break
    return opened_count, merged_count

def analyze_repository(repo_info, idx, headers, people, papers, projects, institutions):
    repo = repo_info['repo_data']
    queries = repo_info['queries']
    repo_full_name = repo.get('full_name')
    owner = repo.get('owner', {}).get('login')
    repo_name = repo.get('name')
    description = repo.get('description') or ''
    topics = repo.get('topics', [])
    readme_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/readme"
    logging.info(f"Analyzing repository [{idx}]: {repo_full_name}")

    # Fetch README content
    try:
        readme_data, _ = github_api_request(readme_url, headers)
    except Exception as e:
        logging.warning(f"Could not retrieve README for {repo_full_name}: {e}")
        readme_data = None
    readme_content = ''
    if readme_data and readme_data.get('content'):
        readme_content = base64.b64decode(
            readme_data.get('content')
        ).decode('utf-8', errors='ignore')

    # Get list of files in the repository
    contents_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/contents"
    try:
        contents, _ = github_api_request(contents_url, headers)
    except Exception as e:
        logging.warning(f"Could not retrieve contents for {repo_full_name}: {e}")
        contents = None
    files = []
    if contents and isinstance(contents, list):
        for content in contents:
            files.append(content.get('name', ''))

    # Get license
    license_info = repo.get('license') or {}
    license_name = license_info.get('name', 'No license')

    # Fetch stars, forks, watchers
    stars_count = repo.get('stargazers_count', 0)
    forks_count = repo.get('forks_count', 0)
    watchers_count = repo.get('watchers_count', 0)
    open_issues_count = repo.get('open_issues_count', 0)

    # Get Languages
    languages_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/languages"
    try:
        languages_data, _ = github_api_request(languages_url, headers)
    except Exception as e:
        logging.warning(f"Could not retrieve languages for {repo_full_name}: {e}")
        languages_data = None
    if languages_data:
        total_bytes = sum(languages_data.values())
        languages_percentages = {
            language: (bytes_count / total_bytes * 100)
            for language, bytes_count in languages_data.items()
        }
        sorted_languages = sorted(
            languages_percentages.items(),
            key=lambda item: item[1],
            reverse=True
        )
        main_language = sorted_languages[0][0] if sorted_languages else 'Unknown'
    else:
        languages_data = {}
        languages_percentages = {}
        main_language = 'Unknown'

    # Extract DOI
    doi = extract_doi_from_repo(owner, repo_name, headers)
    if doi:
        doi = doi.lower()
        paper_data = get_paper_details_from_openalex(doi)
        if paper_data:
            # Collect required information
            paper_title = paper_data.get('title')
            paper_domains = paper_data.get('domains', [])
            authors_info = get_authors_and_institutions(paper_data)
            # Update authors_info with other papers
            authors_info = get_other_papers_by_authors(authors_info, doi)
            # Get first-degree citations
            first_degree_citations = get_first_degree_citations(paper_data)
            total_first_degree_citations = len(first_degree_citations)
            # Get second-degree citations
            second_degree_citations = get_second_degree_citations(first_degree_citations)
            total_second_degree_citations = len(second_degree_citations)
            # Get contributors and participants
            contributors, participants = get_contributors_and_participants(owner, repo_name, headers)
            contributors_count = len(contributors)
            # Get contributors' real names
            contributors_details = get_contributor_details(contributors, headers)
            # Analyze connections
            connections = analyze_connections(contributors, participants, authors_info)
            # Analyze contributor affiliations
            contributor_affiliations = analyze_contributor_affiliations(contributors, headers)
            # Classify contributor roles
            contributor_roles = classify_contributor_roles(contributors)
            # Compile data
            paper_analysis = {
                'doi': doi,
                'paper_title': paper_title,
                'paper_domains': paper_domains,
                'authors_info': authors_info,
                'first_degree_citations': first_degree_citations,
                'second_degree_citations': second_degree_citations,
                'total_first_degree_citations': total_first_degree_citations,
                'total_second_degree_citations': total_second_degree_citations,
                'connections': connections,
                'contributor_affiliations': contributor_affiliations,
                'contributor_roles': contributor_roles,
                'contributors_details': contributors_details
            }
        else:
            logging.warning(f"No paper data found for DOI {doi}")
            paper_analysis = {}
            contributors_count = 0
    else:
        logging.warning(f"No DOI found for repository {repo_full_name}")
        paper_analysis = {}
        # Get contributors even if no DOI is found
        contributors, participants = get_contributors_and_participants(owner, repo_name, headers)
        contributors_count = len(contributors)
        # Get contributors' real names
        contributors_details = get_contributor_details(contributors, headers)
        # Analyze contributor affiliations
        contributor_affiliations = analyze_contributor_affiliations(contributors, headers)
        # Classify contributor roles
        contributor_roles = classify_contributor_roles(contributors)
        paper_analysis['contributor_affiliations'] = contributor_affiliations
        paper_analysis['contributor_roles'] = contributor_roles
        paper_analysis['contributors_details'] = contributors_details

    # Get last commit date
    commits_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/commits"
    try:
        commits_data, _ = github_api_request(commits_url, headers)
        if commits_data:
            last_commit_date = commits_data[0]['commit']['committer']['date']
        else:
            last_commit_date = 'No commits found'
    except Exception as e:
        logging.warning(f"Could not retrieve commits for {repo_full_name}: {e}")
        last_commit_date = 'Error retrieving commits'

    # Check for documentation files
    has_readme = bool(readme_data)
    code_of_conduct_url = f"{GITHUB_API_URL}/repos/{owner}/{repo_name}/community/code_of_conduct"
    try:
        code_of_conduct, _ = github_api_request(code_of_conduct_url, headers)
    except Exception as e:
        logging.warning(f"Could not retrieve code of conduct for {repo_full_name}: {e}")
        code_of_conduct = None
    has_code_of_conduct = code_of_conduct is not None and 'url' in code_of_conduct
    files_to_check = ['CITATION.cff', 'CONTRIBUTING.md', 'GOVERNANCE.md', 'FUNDING.yml', 'funding.json']
    documentation = {file: False for file in files_to_check}
    if contents and isinstance(contents, list):
        for content in contents:
            if content['name'] in documentation:
                documentation[content['name']] = True

    # Get issue counts
    total_issues, open_issues, closed_issues = get_total_issues(owner, repo_name, headers)
    # Get average time to close issues
    average_issue_close_time = get_average_issue_close_time(owner, repo_name, headers)
    # Get issue update frequency
    issue_update_frequency = get_issue_update_frequency(owner, repo_name, headers)
    # Get PR counts
    total_prs, open_prs, closed_prs = get_total_prs(owner, repo_name, headers)
    # Get average time to merge PRs
    average_pr_merge_time = get_average_pr_merge_time(owner, repo_name, headers)
    # Get PR update frequency
    pr_update_frequency = get_pr_update_frequency(owner, repo_name, headers)
    # Get recent commits count (last 30 days)
    recent_commits_count = get_recent_commits_count(owner, repo_name, headers)
    # Get active contributors count (last 30 days)
    active_contributors_count = get_active_contributors_count(owner, repo_name, headers)
    # Get recent issues opened and closed counts (last 30 days)
    recent_issues_opened_count, recent_issues_closed_count = get_recent_issues_counts(owner, repo_name, headers)
    # Get recent PRs opened and merged counts (last 30 days)
    recent_prs_opened_count, recent_prs_merged_count = get_recent_prs_counts(owner, repo_name, headers)
    # Get total downloads and recent downloads
    total_downloads, total_downloads_recent, recent_releases_count = get_total_downloads(owner, repo_name, headers)
    # Get discussion activity count
    discussion_activity_count = get_discussion_activity_count(owner, repo_name, headers)
    # Get stars and forks growth
    stars_growth, forks_growth = get_stars_forks_growth(owner, repo_name, headers)
    # Calculate activity score
    activity_score = calculate_activity_score({
        'recent_commits_count': recent_commits_count,
        'recent_issues_opened_count': recent_issues_opened_count,
        'recent_issues_closed_count': recent_issues_closed_count,
        'recent_prs_opened_count': recent_prs_opened_count,
        'recent_prs_merged_count': recent_prs_merged_count,
        'discussion_activity_count': discussion_activity_count
    })

    # Create Unique IDs
    project_id = f"project_{uuid.uuid4()}"
    projects[project_id] = {
        "id": project_id,
        "full_name": repo_full_name,
        "description": description,
        "license": license_name,
        "last_commit_date": last_commit_date,
        "has_readme": has_readme,
        "has_code_of_conduct": has_code_of_conduct,
        "documentation": documentation,
        "main_language": main_language,
        "languages_percentages": languages_percentages,
        "stars_count": stars_count,
        "forks_count": forks_count,
        "watchers_count": watchers_count,
        "open_issues_count": open_issues_count,
        "contributors": [],
        "associated_papers": [],
        "activity_metrics": {
            "total_issues": total_issues,
            "open_issues": open_issues,
            "closed_issues": closed_issues,
            "average_issue_close_time_days": average_issue_close_time,
            "issue_update_frequency": issue_update_frequency,
            "total_prs": total_prs,
            "open_prs": open_prs,
            "closed_prs": closed_prs,
            "average_pr_merge_time_days": average_pr_merge_time,
            "pr_update_frequency": pr_update_frequency,
            "total_downloads": total_downloads,
            "activity_score": activity_score,
            "recent_commits_count": recent_commits_count,
            "active_contributors_count": active_contributors_count,
            "recent_issues_opened_count": recent_issues_opened_count,
            "recent_issues_closed_count": recent_issues_closed_count,
            "recent_prs_opened_count": recent_prs_opened_count,
            "recent_prs_merged_count": recent_prs_merged_count,
            "stars_growth": stars_growth,
            "forks_growth": forks_growth,
            "recent_releases_count": recent_releases_count,
            "total_downloads_recent": total_downloads_recent,
            "discussion_activity_count": discussion_activity_count
        },
        "queries": list(queries),
        "associated_papers": []
    }

    # Handle Paper Analysis
    if doi and paper_analysis:
        paper_id = f"paper_{uuid.uuid4()}"
        papers[paper_id] = {
            "id": paper_id,
            "doi": paper_analysis.get('doi'),
            "title": paper_analysis.get('paper_title'),
            "domains": paper_analysis.get('paper_domains', []),
            "authors": [],
            "cites_papers": [],
            "cited_by_papers": [],
            "associated_projects": [project_id],
            "concepts": []  # To be filled
        }
        projects[project_id]["associated_papers"].append(paper_id)

        # Process Authors
        for author in paper_analysis.get('authors_info', []):
            # Generate unique person ID
            if author.get('author_id'):
                person_id = f"person_{uuid.uuid4()}"
            else:
                person_id = f"person_{uuid.uuid4()}"
            if person_id not in people:
                people[person_id] = {
                    "id": person_id,
                    "name": author['author_name'],
                    "orcid": author.get('orcid'),
                    "github_username": None,  # If available, otherwise None
                    "affiliations": [],
                    "authored_papers": [],
                    "contributed_projects": [],
                    "other_papers": []
                }
            # Link paper to author
            people[person_id]["authored_papers"].append(paper_id)
            papers[paper_id]["authors"].append(person_id)
            
            # Handle affiliations
            for institution_name in author['institutions']:
                # Check if institution exists
                existing_institution = next((inst for inst in institutions.values() if inst["name"] == institution_name), None)
                if existing_institution:
                    institution_id = existing_institution["id"]
                    institutions[institution_id]["affiliated_people"].append(person_id)
                else:
                    institution_id = f"institution_{uuid.uuid4()}"
                    institutions[institution_id] = {
                        "id": institution_id,
                        "name": institution_name,
                        "location": "",  # Add if available
                        "affiliated_people": [person_id]
                    }
                # Link institution to person
                people[person_id]["affiliations"].append(institution_id)
        
        # Handle Cited Papers
        for citation in paper_analysis.get('first_degree_citations', []):
            cited_paper_id = f"paper_{uuid.uuid4()}"
            papers[cited_paper_id] = {
                "id": cited_paper_id,
                "doi": citation.get('doi'),
                "title": citation.get('title'),
                "domains": citation.get('concepts', []),
                "authors": [],  # To be populated if available
                "cites_papers": [],
                "cited_by_papers": [paper_id],
                "associated_projects": [],
                "concepts": citation.get('concepts', [])
            }
            papers[paper_id]["cited_by_papers"].append(cited_paper_id)
            # Optionally, handle authors of cited papers similarly
            # ...

        # Handle Second-degree Citations
        for second_citation in paper_analysis.get('second_degree_citations', []):
            second_paper_id = f"paper_{uuid.uuid4()}"
            papers[second_paper_id] = {
                "id": second_paper_id,
                "doi": second_citation.get('doi'),
                "title": second_citation.get('title'),
                "domains": second_citation.get('concepts', []),
                "authors": [],  # To be populated if available
                "cites_papers": [paper_id],
                "cited_by_papers": [],
                "associated_projects": [],
                "concepts": second_citation.get('concepts', [])
            }
            # Optionally, link back to the first-degree paper
            # ...

        # Handle Connections (optional, depending on analysis needs)
        # ...

    # Handle Contributors (even if no DOI is found)
    if 'contributor_affiliations' in paper_analysis:
        for contributor in paper_analysis['contributor_affiliations']:
            username = contributor['username']
            affiliation = contributor['affiliation']
            # Check if person already exists
            existing_person = next((p for p in people.values() if p["github_username"] == username), None)
            if existing_person:
                person_id = existing_person["id"]
                if affiliation:
                    # Check if institution exists
                    existing_institution = next((inst for inst in institutions.values() if inst["name"] == affiliation), None)
                    if existing_institution:
                        institution_id = existing_institution["id"]
                        institutions[institution_id]["affiliated_people"].append(person_id)
                    else:
                        institution_id = f"institution_{uuid.uuid4()}"
                        institutions[institution_id] = {
                            "id": institution_id,
                            "name": affiliation,
                            "location": "",  # Add if available
                            "affiliated_people": [person_id]
                        }
                    # Link institution to person
                    people[person_id]["affiliations"].append(institution_id)
            else:
                # Create new person entry
                person_id = f"person_{uuid.uuid4()}"
                people[person_id] = {
                    "id": person_id,
                    "name": contributor.get('real_name') or username,
                    "orcid": None,
                    "github_username": username,
                    "affiliations": [],
                    "authored_papers": [],
                    "contributed_projects": [project_id],
                    "other_papers": []
                }
                projects[project_id]["contributors"].append(person_id)
                if affiliation:
                    # Check if institution exists
                    existing_institution = next((inst for inst in institutions.values() if inst["name"] == affiliation), None)
                    if existing_institution:
                        institution_id = existing_institution["id"]
                        institutions[institution_id]["affiliated_people"].append(person_id)
                    else:
                        institution_id = f"institution_{uuid.uuid4()}"
                        institutions[institution_id] = {
                            "id": institution_id,
                            "name": affiliation,
                            "location": "",  # Add if available
                            "affiliated_people": [person_id]
                        }
                    # Link institution to person
                    people[person_id]["affiliations"].append(institution_id)

    # Compile data
    repo_data = {
        'repo_number': idx,
        'full_name': repo_full_name,
        'description': description,
        'license': license_name,
        'last_commit_date': last_commit_date,
        'has_readme': has_readme,
        'has_code_of_conduct': has_code_of_conduct,
        'documentation': documentation,
        'main_language': main_language,
        'languages_percentages': languages_percentages,
        'stars_count': stars_count,
        'forks_count': forks_count,
        'watchers_count': watchers_count,
        'open_issues_count': open_issues_count,
        'contributors_count': contributors_count,
        'activity_metrics': {
            "total_issues": total_issues,
            "open_issues": open_issues,
            "closed_issues": closed_issues,
            "average_issue_close_time_days": average_issue_close_time,
            "issue_update_frequency": issue_update_frequency,
            "total_prs": total_prs,
            "open_prs": open_prs,
            "closed_prs": closed_prs,
            "average_pr_merge_time_days": average_pr_merge_time,
            "pr_update_frequency": pr_update_frequency,
            "total_downloads": total_downloads,
            "activity_score": activity_score,
            "recent_commits_count": recent_commits_count,
            "active_contributors_count": active_contributors_count,
            "recent_issues_opened_count": recent_issues_opened_count,
            "recent_issues_closed_count": recent_issues_closed_count,
            "recent_prs_opened_count": recent_prs_opened_count,
            "recent_prs_merged_count": recent_prs_merged_count,
            "stars_growth": stars_growth,
            "forks_growth": forks_growth,
            "recent_releases_count": recent_releases_count,
            "total_downloads_recent": total_downloads_recent,
            "discussion_activity_count": discussion_activity_count
        },
        'associated_papers': [],
        'queries': list(queries)
    }

    # If there's associated paper, link it to the project
    if doi and paper_analysis:
        paper_id = [pid for pid, pdata in papers.items() if pdata.get('doi') == doi]
        if paper_id:
            repo_data['associated_papers'].extend(paper_id)

    projects[project_id]['activity_metrics'] = repo_data['activity_metrics']
    projects[project_id]['contributors'] = [person['id'] for person in people.values() if project_id in person['contributed_projects']]
    
    logging.info(f"Repository analyzed: {repo_full_name}")
    return

def write_to_json(people, papers, projects, institutions, output_filename_json):
    """
    Writes the collected entities to a structured JSON file.
    """
    data = {
        "people": list(people.values()),
        "papers": list(papers.values()),
        "projects": list(projects.values()),
        "institutions": list(institutions.values())
    }
    with open(output_filename_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logging.info(f"JSON data written to {output_filename_json}")

def write_entity_csv(entity_list, headers, filename):
    """
    Writes a list of entities to a CSV file.
    """
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for entity in entity_list:
            # Convert lists to semicolon-separated strings for CSV compatibility
            for key, value in entity.items():
                if isinstance(value, list):
                    entity[key] = '; '.join(value)
                elif isinstance(value, dict):
                    entity[key] = json.dumps(value)
            writer.writerow(entity)
    logging.info(f"CSV data written to {filename}")

def convert_sets_to_lists(obj):
    """
    Recursively converts sets to lists in a data structure.
    """
    if isinstance(obj, dict):
        return {k: convert_sets_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_sets_to_lists(element) for element in obj]
    elif isinstance(obj, set):
        return list(obj)
    else:
        return obj

def parse_repository_input(repo_input):
    """
    Parses repository input and extracts owner and repo_name.
    Supports both 'owner/repo' format and full GitHub URLs.
    """
    repo_input = repo_input.strip()
    if repo_input.startswith('http://') or repo_input.startswith('https://'):
        # Parse URL
        parsed_url = urllib.parse.urlparse(repo_input)
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo_name = path_parts[1]
            return owner, repo_name
        else:
            raise ValueError(f"Invalid GitHub URL format: {repo_input}")
    else:
        # Assume 'owner/repo' format
        if '/' not in repo_input:
            raise ValueError(f"Invalid repository format: {repo_input}")
        owner, repo_name = repo_input.split('/', 1)
        return owner, repo_name

# Main script
if __name__ == "__main__":
    start_time = time.time()

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Repository Analysis Script')
    parser.add_argument('--repos', nargs='+', help='List of repositories in the format owner/repo or full GitHub URLs')
    parser.add_argument('--limit', '-l', type=int, help='Limit processing to the first N repositories')
    args = parser.parse_args()

    # GitHub authentication
    load_dotenv()
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logging.error("GITHUB_TOKEN not found in .env file. Please create a .env file with your GitHub token.")
        exit(1)
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    # User input if repos are not provided via arguments
    if not args.repos:
        repositories_input = []
        while True:
            repo_input = input("Enter a repository in the format owner/repo or full GitHub URL (or 'n' to stop): ").strip()
            if repo_input.lower() == 'n':
                break
            repositories_input.append(repo_input)
        if not repositories_input:
            logging.error("No repositories provided. Exiting.")
            exit(1)
    else:
        repositories_input = args.repos

    # Build query terms
    query_terms = []
    for repo_full_name in repositories_input:
        try:
            owner, repo_name = parse_repository_input(repo_full_name)
            query_terms.append(f'repo:{owner}/{repo_name}')
        except ValueError as e:
            logging.warning(str(e))
            continue

    # Search repositories
    repositories = search_repositories_with_queries(query_terms, headers)
    logging.info(f"Total repositories found: {len(repositories)}")

    # Limit processing if --limit flag is set
    if args.limit:
        limit_count = args.limit
        logging.info(f"Limiting processing to the first {limit_count} repositories due to --limit flag.")
        # Convert repositories dictionary to a list of items and take the first N
        repositories_items = list(repositories.items())[:limit_count]
    else:
        repositories_items = list(repositories.items())

    # Initialize entity collections
    people = {}
    papers = {}
    projects = {}
    institutions = {}

    # Analyze repositories with a progress bar
    all_repo_data = []
    total_repos = len(repositories_items)

    with tqdm(total=total_repos, desc='Analyzing Repositories', unit='repo', position=0) as pbar:
        for idx, (repo_id, repo_info) in enumerate(repositories_items, start=1):
            logging.info(f"Processing repository {idx}/{total_repos}: {repo_info['repo_data'].get('full_name', '')}")
            analyze_repository(
                repo_info,
                idx,
                headers,
                people,
                papers,
                projects,
                institutions
            )
            pbar.update(1)  # Update the main repositories progress bar

    # Convert all sets in collections to lists if necessary
    all_repo_data_serializable = {
        "people": convert_sets_to_lists(list(people.values())),
        "papers": convert_sets_to_lists(list(papers.values())),
        "projects": convert_sets_to_lists(list(projects.values())),
        "institutions": convert_sets_to_lists(list(institutions.values()))
    }

    # Output results
    output_filename_json = "analysis_results.json"
    write_to_json(people, papers, projects, institutions, output_filename_json)

    # Optionally, write separate CSVs for each entity
    # Example for people
    people_headers = ['id', 'name', 'orcid', 'github_username', 'affiliations', 'authored_papers', 'contributed_projects', 'other_papers']
    write_entity_csv(list(people.values()), people_headers, "people.csv")

    # Example for papers
    papers_headers = ['id', 'doi', 'title', 'domains', 'authors', 'cites_papers', 'cited_by_papers', 'associated_projects', 'concepts']
    write_entity_csv(list(papers.values()), papers_headers, "papers.csv")

    # Example for projects
    projects_headers = [
        'id', 'full_name', 'description', 'license', 'last_commit_date', 'has_readme',
        'has_code_of_conduct', 'documentation', 'main_language', 'languages_percentages',
        'stars_count', 'forks_count', 'watchers_count', 'open_issues_count',
        'contributors', 'associated_papers', 'activity_metrics', 'queries'
    ]
    write_entity_csv(list(projects.values()), projects_headers, "projects.csv")

    # Example for institutions
    institutions_headers = ['id', 'name', 'location', 'affiliated_people']
    write_entity_csv(list(institutions.values()), institutions_headers, "institutions.csv")

    end_time = time.time()
    total_runtime = end_time - start_time
    logging.info(f"Total runtime: {total_runtime:.2f} seconds")
