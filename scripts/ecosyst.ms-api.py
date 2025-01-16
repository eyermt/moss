import csv
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

import requests

# Display example URLs for user guidance
print("""Example URLs: \n
        https://papers.ecosyste.ms/api/v1/projects/pypi/scikit-learn \n
        https://papers.ecosyste.ms/api/v1/projects/pypi/keras \n
        https://papers.ecosyste.ms/api/v1/projects/cran/OpenML \n
        """)

# Prompt the user for project URL(s) and split the input into a list of URLs
project_url = input(
    'Please enter the ecosyste.ms URL for your project of interest: '
).split()

# Initialize global variables for storing unique entities and rows for CSV output
row_list = Queue()  # Queue to store rows for the CSV file
institution_set = set()  # Set to keep track of unique institutions
people_set = set()  # Set to keep track of unique people
paper_set = set()  # Set to keep track of unique papers
project_set = set()  # Set to keep track of unique projects
sdg_set = set()  # Set to keep track of unique SDGs
concept_set = set()  # Set to keep track of unique concepts
domain_set = set()  # Set to keep track of unique domains

project_url_set = set()  # Set to keep track of project URLs
headers = {'accept': 'application/json'}  # Headers for HTTP requests

# Define the field names for the CSV file
csv_field_names = [
    'ID',
    'Label',
    'Name',
    'ORCID',
    'Persons Affiliated Institutions',
    'DOI',
    'Projects/Packages Cited',
    'Authors',
    'Homepage',
    'repository_url',
    'Sustainable Development Goals',
    'sdg_score',
    'Concepts',
    'Wikidata',
    'Concept_level',
    'Domains',
    'Is_major_topic',
]


# Function to process individual papers and extract relevant data
def process_paper(paper_url):
    try:
        # Fetch the paper data from the given URL
        paper_response = requests.get(paper_url, headers=headers, timeout=10)
        paper_dict = paper_response.json()

        # Extract authors and add them to the set and row list
        paper_author_names = []
        if paper_dict['openalex_data']:
            for authorship in paper_dict['openalex_data']['authorships']:
                paper_author_names.append(authorship['author']['display_name'])

                author_dict = authorship['author']
                if author_dict['id'] not in people_set:
                    people_set.add(author_dict['id'])
                    row_list.put(
                        {
                            'ID': author_dict['id'],
                            'Label': 'Person',
                            'Name': author_dict['display_name'],
                            'ORCID': author_dict['orcid'],
                            'Persons Affiliated Institutions': ' | '.join(
                                inst['display_name']
                                for inst in authorship['institutions']
                            ),
                        }
                    )

        # process paper mentions and collect list of comentioned projects (project_ursl)
        paper_mentions = process_paper_mentions(paper_dict['mentions_url'])

        # Add the paper to the set and row list if it's not already present
        if paper_dict['openalex_id'] not in paper_set:
            paper_set.add(paper_dict['openalex_id'])

            if paper_dict['openalex_data']:
                for authorship in paper_dict['openalex_data']['authorships']:
                    for institution in authorship['institutions']:
                        if institution['id'] not in institution_set:
                            institution_set.add(institution['id'])
                            row_list.put(
                                {
                                    'ID': institution['id'],
                                    'Label': 'Institution',
                                    'Name': institution['display_name'],
                                }
                            )
                # Extract SDGs, concepts, and domains from the paper
                paper_sdgs = []
                for sdg in paper_dict['openalex_data']['sustainable_development_goals']:
                    paper_sdgs.append(sdg['display_name'])
                    if sdg['id'] not in sdg_set:
                        sdg_set.add(sdg['id'])
                        row_list.put(
                            {
                                'ID': sdg['id'],
                                'Label': 'SDG',
                                'Name': sdg['display_name'],
                                'sdg_score': sdg['score'],
                            }
                        )
                paper_concepts = []
                for concept in paper_dict['openalex_data']['concepts']:
                    paper_concepts.append(concept['display_name'])
                    if concept['id'] not in concept_set:
                        concept_set.add(concept['id'])
                        row_list.put(
                            {
                                'ID': concept['id'],
                                'Label': 'Concept',
                                'Name': concept['display_name'],
                                'Wikidata': concept['wikidata'],
                                'Concept_level': concept['level'],
                            }
                        )
                paper_domains = []
                for domain in paper_dict['openalex_data']['mesh']:
                    paper_domains.append(domain['descriptor_name'])
                    if domain['descriptor_ui'] not in domain_set:
                        domain_set.add(domain['descriptor_ui'])
                        row_list.put(
                            {
                                'ID': domain['descriptor_ui'],
                                'Label': 'Domain',
                                'Name': domain['descriptor_name'],
                                'Is_major_topic': domain['is_major_topic'],
                            }
                        )
                # Add the paper information to the row list for the CSV
                row_list.put(
                    {
                        'ID': paper_dict['openalex_id'],
                        'Label': 'Paper',
                        'Name': paper_dict['title'],
                        'DOI': paper_dict['doi'],
                        'Authors': ' | '.join(paper_author_names),
                        'Projects/Packages Cited': ' | '.join(paper_mentions),
                        'Sustainable Development Goals': ' | '.join(paper_sdgs),
                        'Concepts': ' | '.join(paper_concepts),
                        'Domains': ' | '.join(paper_domains),
                    }
                )
    except requests.exceptions.RequestException as e:
        # Handle request exceptions
        print(f'Request failed for paper {paper_url}: {e}')
    except json.decoder.JSONDecodeError:
        # Handle JSON decoding errors
        print(f'JSON decode error for paper {paper_url}')


# Function to process mentions in papers and return the project mentions
def process_paper_mentions(paper_mentions_url):
    paper_mentions = []
    try:
        # Fetch mentions data from the given URL
        paper_mentions_response = requests.get(
            paper_mentions_url, headers=headers, timeout=10
        )
        paper_mentions_dict = paper_mentions_response.json()

        # Extract project mentions from the response and add them to the set
        paper_mentions_list = [
            paper_mention['project_url'] for paper_mention in paper_mentions_dict
        ]
        project_url_set.update(paper_mentions_list)

        for project_url in paper_mentions_list:
            try:
                # Fetch project data for each mention and process it
                project_response = requests.get(
                    project_url, headers=headers, timeout=10
                )
                proj_dict = project_response.json()

                paper_mentions.append(f"{proj_dict['ecosystem']}:{proj_dict['name']}")

                if proj_dict['package']:
                    home = proj_dict['package']['homepage']
                    repo = proj_dict['package']['repository_url']
                else:
                    home = ''
                    repo = ''

                # Add the project information to the set and row list
                if proj_dict['czi_id'] not in project_set:
                    project_set.add(proj_dict['czi_id'])
                    row_list.put(
                        {
                            'ID': proj_dict['czi_id'],
                            'Label': 'Project',
                            'Name': f"{proj_dict['ecosystem']}:{proj_dict['name']}",
                            'Homepage': home,
                            'repository_url': repo,
                        }
                    )
            except requests.exceptions.RequestException as e:
                # Handle request exceptions for project mentions
                print(f'Request failed for project {project_url}: {e}')
            except json.decoder.JSONDecodeError:
                # Handle JSON decoding errors for project mentions
                print(f'JSON decode error for project {project_url}')
    except requests.exceptions.RequestException as e:
        # Handle request exceptions for paper mentions
        print(f'Request failed for mentions {paper_mentions_url}: {e}')
    except json.decoder.JSONDecodeError:
        # Handle JSON decoding errors for paper mentions
        print(f'JSON decode error for mentions {paper_mentions_url}')

    return paper_mentions


# Function to process multiple projects concurrently
def process_projects(project_urls):
    with ThreadPoolExecutor(max_workers=20) as executor:
        # Submit tasks for processing each project URL
        futures = [
            executor.submit(process_project, project_u) for project_u in project_urls
        ]
        for future in as_completed(futures):
            future.result()


# Function to process individual projects and extract relevant data
def process_project(project_u):
    try:
        # Fetch project data from the given URL
        response = requests.get(project_u, headers=headers, timeout=10)
        project_dict = response.json()

        if project_dict['package']:
            home = project_dict['package']['homepage']
            repo = project_dict['package']['repository_url']
        else:
            home = ''
            repo = ''

        # Add the project to the set and row list
        project_set.add(project_dict['czi_id'])
        row_list.put(
            {
                'ID': project_dict['czi_id'],
                'Label': 'Project',
                'Name': f"{project_dict['ecosystem']}:{project_dict['name']}",
                'Homepage': home,
                'repository_url': repo,
            }
        )

        # Fetch and process mentions associated with the project
        project_mentions_url = f"{project_dict['mentions_url']}?page=1&per_page=1000"
        mentions_response = requests.get(
            project_mentions_url, headers=headers, timeout=10
        )
        mentions_dict = mentions_response.json()

        print(f'Querying: {project_u}')
        print(
            f"There are {mentions_response.headers['total-pages']} pages of mentions to fetch."
        )
        print(f"For a total of: {mentions_response.headers['total-count']} papers")

        paper_urls_list = []
        total_pages = int(mentions_response.headers['total-pages'])
        for page_num in range(1, total_pages + 1):
            project_mentions_url = (
                f"{project_dict['mentions_url']}?page={page_num}&per_page=1000"
            )
            mentions_dict = requests.get(
                project_mentions_url, headers=headers, timeout=10
            ).json()

            paper_urls_list.extend([mention['paper_url'] for mention in mentions_dict])

        # Process each paper mentioned in the project concurrently
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(process_paper, paper_url)
                for paper_url in paper_urls_list
            ]
            paper_counter = 0
            for future in as_completed(futures):
                future.result()
                paper_counter += 1
                print(
                    f"Processed paper: {paper_counter} of {mentions_response.headers['total-count']}"
                )
    except requests.exceptions.RequestException as e:
        # Handle request exceptions for projects
        print(f'Request failed for project {project_u}: {e}')
    except json.decoder.JSONDecodeError:
        # Handle JSON decoding errors for projects
        print(f'JSON decode error for project {project_u}')


# Function to write queued rows to the CSV file
def write_to_csv():
    with open('ecosystms_output.csv', mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=csv_field_names)
        while not row_list.empty():
            writer.writerow(row_list.get())


# Function to check the scope of project mentions and estimate average mentions
def check_scope():
    print(f'This project has {len(project_url_set)} co-mentioned projects')

    mentions_counts = []
    try:
        # Fetch and calculate the number of mentions for each project URL
        for project_u in project_url_set:
            response = requests.get(project_u, headers=headers, timeout=10)
            project_dict = response.json()

            project_mentions_url = f"{project_dict['mentions_url']}?page=1&per_page=1"
            mentions_response = requests.get(
                project_mentions_url, headers=headers, timeout=10
            )
            mentions_counts.append(int(mentions_response.headers['total-count']))

        # Calculate and print the average mentions per project
        mentions_average = sum(mentions_counts) / len(mentions_counts)
        print(f'With an average of: {mentions_average} mentions per project')
    except requests.exceptions.RequestException as e:
        # Handle request exceptions during scope check
        print(f'Request failed during scope check: {e}')
    except json.decoder.JSONDecodeError:
        # Handle JSON decoding errors during scope check
        print('JSON decode error during scope check')

    return sum(mentions_counts)


# Main execution starts here
# Initialize the CSV file with headers
with open('ecosystms_output.csv', mode='w', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=csv_field_names)
    writer.writeheader()

# Process the initial set of project URLs provided by the user
process_projects(project_url)

# Estimate the number of papers to be processed if the user chooses to continue
papers_estimate = check_scope()

# Ask the user if they want to continue processing more papers
continue_yn = input(
    f'Would you like to continue processing {papers_estimate} more papers? y/n: '
)

# Process all mentioned projects if the user agrees
if continue_yn == 'y':
    project_url_set_copy = project_url_set.copy()
    process_projects(project_url_set_copy)


# Write processed data to the CSV file
write_to_csv()
print('All rows appended to CSV file successfully!')
