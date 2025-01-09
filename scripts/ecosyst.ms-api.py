import csv
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# Prompt for project URL(s)
project_url = input(
    'Please enter the ecosyste.ms URL for your project of interest: '
).split()
# project_url = ['https://papers.ecosyste.ms/api/v1/projects/pypi/scikit-learn']  #2431 mentions
# project_url = ['https://papers.ecosyste.ms/api/v1/projects/pypi/keras']         #141 mentions
# project_url = ['https://papers.ecosyste.ms/api/v1/projects/cran/OpenML']        #21 mentions
project_mentions_yn = input(
    'Would you like to create nodes for every project mentioned in papers that mention your project? y/n: '
)

# Declare global variables
row_list = []
institution_set = set()
people_set = set()
paper_set = set()
project_set = set()
sdg_set = set()
concept_set = set()
domain_set = set()

project_url_set = set()
headers = {'accept': 'application/json'}
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


def process_paper(paper_url):
    paper_response = requests.get(paper_url, headers=headers)
    try:
        paper_dict = paper_response.json()

        paper_author_names = []
        if paper_dict['openalex_data'] is not None:
            for authorship in paper_dict['openalex_data']['authorships']:
                paper_author_names.append(authorship['author']['display_name'])

        if project_mentions_yn == 'y':
            paper_mentions = process_paper_mentions(paper_dict['mentions_url'])
        else:
            paper_mentions = ''

        if paper_dict['openalex_id'] not in paper_set:
            paper_set.add(paper_dict['openalex_id'])

            if paper_dict['openalex_data'] is not None:
                for authorship in paper_dict['openalex_data']['authorships']:
                    author_institutions = []
                    for institution in authorship['institutions']:
                        author_institutions.append(institution['display_name'])
                        if institution['id'] not in institution_set:
                            institution_set.add(institution['id'])
                            row_list.append(
                                {
                                    'ID': institution['id'],
                                    'Label': 'Institution',
                                    'Name': institution['display_name'],
                                }
                            )
                paper_sdgs = []
                for sdg in paper_dict['openalex_data']['sustainable_development_goals']:
                    paper_sdgs.append(sdg['display_name'])
                    if sdg['id'] not in sdg_set:
                        sdg_set.add(sdg['id'])
                        row_list.append(
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
                        row_list.append(
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
                    if domain['descriptor_ui'] not in concept_set:
                        domain_set.add(domain['descriptor_ui'])
                        row_list.append(
                            {
                                'ID': domain['descriptor_ui'],
                                'Label': 'Domain',
                                'Name': domain['descriptor_name'],
                                'Is_major_topic': domain['is_major_topic'],
                            }
                        )

            row_list.append(
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
            author_dict = authorship['author']
            if author_dict['id'] not in people_set:
                people_set.add(author_dict['id'])
                row_list.append(
                    {
                        'ID': author_dict['id'],
                        'Label': 'Person',
                        'Name': author_dict['display_name'],
                        'ORCID': author_dict['orcid'],
                        'Persons Affiliated Institutions': ' | '.join(
                            author_institutions
                        ),
                    }
                )
    except json.decoder.JSONDecodeError:
        paper_author_names = []  # meaningless


def process_paper_mentions(paper_mentions_url):
    paper_mentions_response = requests.get(paper_mentions_url, headers=headers)
    try:
        paper_mentions_dict = paper_mentions_response.json()

        paper_mentions_list = []
        for paper_mention in paper_mentions_dict:
            paper_mentions_list.append(paper_mention['project_url'])
            project_url_set.add(paper_mention['project_url'])

        paper_mentions = []
        for project_url in paper_mentions_list:
            project_response = requests.get(project_url, headers=headers)
            try:
                proj_dict = project_response.json()

                paper_mentions.append(proj_dict['ecosystem'] + ':' + proj_dict['name'])

                if proj_dict['package'] is not None:
                    home = proj_dict['package']['homepage']
                    repo = proj_dict['package']['repository_url']
                else:
                    home = ''
                    repo = ''

                if proj_dict['czi_id'] not in project_set:
                    project_set.add(proj_dict['czi_id'])
                    row_list.append(
                        {
                            'ID': proj_dict['czi_id'],
                            'Label': 'Project',
                            'Name': proj_dict['ecosystem'] + ':' + proj_dict['name'],
                            'Homepage': home,
                            'repository_url': repo,
                        }
                    )
            except json.decoder.JSONDecodeError:
                paper_mentions = []
    except json.decoder.JSONDecodeError:
        paper_mentions = []

    return paper_mentions


def process_projects(project_urls):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(process_project, project_u) for project_u in project_urls
        ]
        for future in as_completed(futures):
            future.result()


def process_project(project_u):
    response = requests.get(project_u, headers=headers)
    try:
        project_dict = response.json()

        if project_dict['package'] is not None:
            home = project_dict['package']['homepage']
            repo = project_dict['package']['repository_url']
        else:
            home = ''
            repo = ''

        project_set.add(project_dict['czi_id'])
        row_list.append(
            {
                'ID': project_dict['czi_id'],
                'Label': 'Project',
                'Name': project_dict['ecosystem'] + ':' + project_dict['name'],
                'Homepage': home,
                'repository_url': repo,
            }
        )

        project_mentions_url = project_dict['mentions_url'] + '?page=1&per_page=1000'

        mentions_response = requests.get(project_mentions_url, headers=headers)
        mentions_dict = mentions_response.json()

        print('Querying: ' + project_u)
        print(
            'There are '
            + mentions_response.headers['total-pages']
            + ' pages of mentions to fetch.'
        )
        print('For a total of: ' + mentions_response.headers['total-count'] + ' papers')

        paper_urls_list = []
        total_pages = int(mentions_response.headers['total-pages'])
        page_num = 1
        while page_num <= total_pages:
            project_mentions_url = (
                project_dict['mentions_url']
                + '?page='
                + str(page_num)
                + '&per_page=1000'
            )
            mentions_dict = requests.get(project_mentions_url, headers=headers).json()

            for mention in mentions_dict:
                paper_urls_list.append(mention['paper_url'])
            page_num += 1

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(process_paper, paper_url)
                for paper_url in paper_urls_list
            ]
            paper_counter = 0
            for future in as_completed(futures):
                future.result()
                paper_counter += 1
                print(
                    'Processed paper: '
                    + str(paper_counter)
                    + ' of '
                    + mentions_response.headers['total-count']
                )

        with open('ecosystms_output.csv', mode='a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=csv_field_names)
            for row in row_list:
                writer.writerow(row)
        row_list.clear()
        print('All rows appended to CSV file successfully!')
    except json.decoder.JSONDecodeError:
        row_list.clear()


def check_scope():
    print('This project has ' + str(len(project_url_set)) + ' co-mentioned projects')

    mentions_counts = []

    try:
        mentions_average = 0
        for project_u in project_url_set:
            response = requests.get(project_u, headers=headers)
            project_dict = response.json()

            project_mentions_url = project_dict['mentions_url'] + '?page=1&per_page=1'

            mentions_response = requests.get(project_mentions_url, headers=headers)
            mentions_counts.append(int(mentions_response.headers['total-count']))
            mentions_average = sum(mentions_counts) / len(mentions_counts)

        print('With an average of: ' + str(mentions_average) + ' mentions per project')
    except json.decoder.JSONDecodeError:
        mentions_counts = [0]
    return sum(mentions_counts)


# Main
with open('ecosystms_output.csv', mode='w', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=csv_field_names)
    writer.writeheader()

process_projects(project_url)

papers_estimate = check_scope()

continue_yn = input(
    'Would you like to continue processing '
    + str(papers_estimate)
    + ' more papers? y/n: '
)

if continue_yn == 'y':
    project_url_set_copy = project_url_set.copy()
    process_projects(project_url_set_copy)
