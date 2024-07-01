import json
import csv
import requests

#Prompt for project url(s)
projectURL = input("Plz enter the ecosyste.ms url for your project of interest: ").split()
#projectURL = ['https://papers.ecosyste.ms/api/v1/projects/pypi/scikit-learn']  #2431 mentions
#projectURL = ['https://papers.ecosyste.ms/api/v1/projects/pypi/keras']         #141 mentions
#projectURL = ['https://papers.ecosyste.ms/api/v1/projects/cran/OpenML']        #21 mentions
projectMentionsYN = input("Would you like to create nodes for every project mentioned in papers that mention your project? y/n: ")


#Declare global variables
rowList = []
institutionSet = set()
peopleSet = set()
paperSet = set()
projectSet = set()

#Process papers that mention project & prepare rows for writing to csv
def processPaper(paperURL): 
    paperResponse = requests.get(paperURL, headers=headers)
    paperDict = paperResponse.json()

    #Collect paper author names for paper row
    paperAuthorNames = []
    if paperDict["openalex_data"] is not None:
        for authorship in paperDict["openalex_data"]["authorships"]:
            paperAuthorNames.append( authorship['author']['display_name'] )

    #Run processPaperMentions to collect software_mentions for paper row
    if projectMentionsYN == "y":
        paperMentions = processPaperMentions(paperDict["mentions_url"])
    else:
        paperMentions = ""

    #Create paper row if unique
    if paperDict["openalex_id"] not in paperSet:
        paperSet.add(paperDict["openalex_id"])
        rowList.append( {'id': paperDict['openalex_id'], 'type': "Paper", 'title': paperDict['title'], 'doi': paperDict['doi'], 'authors': paperAuthorNames, 'software_mentions': paperMentions } )

    if paperDict["openalex_data"] is not None:
        #Loop through all authors of paper
        for authorship in paperDict["openalex_data"]["authorships"]:
            
            #Create institution rows for author's institutions if unique
            thisAuthorInstitutions = []
            #institution = authorship["Institutions"][0]            #uncomment to only add instution row for primary institution
            for institution in authorship["institutions"]:          #would need to comment some of this out too
                thisAuthorInstitutions.append(institution['display_name']) #collect author institution names for author row
                if institution["id"] not in institutionSet:
                    institutionSet.add(institution["id"])
                    rowList.append( {'id': institution['id'], 'type': "Institution", 'display_name': institution['display_name'] } )

            #Create person row for author if unique
            authorDict = authorship["author"]
            if authorDict['id'] not in peopleSet:
                peopleSet.add(authorDict['id'])
                rowList.append( {'type': "Person"} | authorDict | {'institutions': thisAuthorInstitutions})

    return(rowList)

#Get all projects mentioned in paper and create project rows
def processPaperMentions(paperMentionsURL):
    paperMentionsResponse = requests.get(paperMentionsURL, headers=headers)
    paperMentionsDict = paperMentionsResponse.json()

    #Get project URLs
    paperMentionsList = []
    for paperMention in paperMentionsDict:
        paperMentionsList.append(paperMention["project_url"])

    #Iterate through project URLs and create project rows if unique
    thisPapersMentions = []
    for projectURL in paperMentionsList:
        projectResponse = requests.get(projectURL, headers=headers)
        try:
            projDict = projectResponse.json()

            thisPapersMentions.append(projDict["ecosystem"] + ":" + projDict["name"])
            
            if projDict["package"] is not None:
                home = projDict["package"]["homepage"]
                repo = projDict["package"]["repository_url"]
            else:
                home = ""
                repo = ""

            if projDict["czi_id"] not in projectSet:
                projectSet.add(projDict["czi_id"])
                rowList.append( {'id': projDict["czi_id"], 'type': "Project", 'display_name':projDict["ecosystem"]+":"+projDict["name"], 'homepage': home, 'repository_url': repo } )
        except json.decoder.JSONDecodeError:
            thisPaperMentions=[]

    return(thisPapersMentions)

#Main 
#Process all projects given via input
for projectU in projectURL:
    rowList = []

    #Recieve Project info
    headers = {'accept': 'application/json',}
    response = requests.get(projectU, headers=headers)
    projectDict = response.json()

    if projectDict["package"] is not None:
        home = projectDict["package"]["homepage"]
        repo = projectDict["package"]["repository_url"]
    else:
        home = ""
        repo = ""
    
    #Create project row
    projectSet.add(projectDict["czi_id"])
    rowList.append( {'id': projectDict["czi_id"], 'type': "Project", 'display_name':projectDict["ecosystem"]+":"+projectDict["name"], 
        'homepage': home, 'repository_url': repo } )

    #Get Mentions URL
    projectMentionsURL = projectDict["mentions_url"]+"?page=1&per_page=1000"

    #Query mentions
    mentionsResponse = requests.get(projectMentionsURL, headers=headers)
    mentionsDict = mentionsResponse.json()

    #Print info about query scope
    print("Querying: " + projectU)
    print("There are " + mentionsResponse.headers['total-pages'] + " pages of mentions to fetch.")
    print("For a total of: " + mentionsResponse.headers['total-count'] + " papers")

    #Get Paper URLs
    paperURLsList = []
    totalPages = int(mentionsResponse.headers['total-pages'])
    pageNum = 1
    while pageNum <= totalPages:
        projectMentionsURL = projectDict["mentions_url"] + "?page=" + str(pageNum) + "&per_page=1000"
        mentionsDict = requests.get(projectMentionsURL, headers=headers).json() 

        for mention in mentionsDict:{
            paperURLsList.append(mention["paper_url"])
        }
        pageNum+=1

    #Iterate through all papers that mention project
    paperCounter = 0
    for paperURL in paperURLsList:
        processPaper(paperURL)
        paperCounter+=1
        print("Processed paper: " + str(paperCounter) + " of " + mentionsResponse.headers['total-count'])

    #Write all rows to CSV file
    with open('ecosystms_output.csv', mode='w', newline='') as file:
        fieldnames = ['id', 'type', 'display_name', 'orcid', 'institutions', 'title', 'doi', 'software_mentions', 'authors', 'homepage', 'repository_url']

        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rowList:
            writer.writerow(row)

    print("All rows written to csv file successfully!")
