import json
import csv
import requests

#prompt for project url
projectURL = input("Plz enter the ecosyste.ms url for your project of interest: ")
#projectURL = 'https://papers.ecosyste.ms/api/v1/projects/pypi/scikit-learn'

#for projectU in projectURL:

#Recieve Project info
headers = {'accept': 'application/json',}
response = requests.get(projectURL, headers=headers)
projectDict = response.json()

#Get Mentions URL
projectMentionsURL = projectDict["mentions_url"]+"?page=1&per_page=1000"
#print(projectMentionsURL)

#query mentions
mentionsResponse = requests.get(projectMentionsURL, headers=headers)
mentionsDict = mentionsResponse.json()

print("There are " + mentionsResponse.headers['total-pages'] + " pages of mentions to fetch.")
print("For a total of: " + mentionsResponse.headers['total-count'])


#Get Paper URLs
paperURLsList = []
#for mention in mentionsDict:{
#    paperURLsList.append(mention["paper_url"])
#}

totalPages = int(mentionsResponse.headers['total-pages'])
pageNum = 1
while pageNum <= totalPages:
    projectMentionsURL = projectDict["mentions_url"] + "?page=" + str(pageNum) + "&per_page=1000"
    mentionsDict = requests.get(projectMentionsURL, headers=headers).json() 

    for mention in mentionsDict:{
        paperURLsList.append(mention["paper_url"])
    }

    pageNum+=1



####switch for testing with just one paper
#paperURLsList.append(mentionsDict[0]["paper_url"])
print(paperURLsList)


rowList = []
institutionSet = set()

def getPaperAuthors(paperURL): 
    paperResponse = requests.get(paperURL, headers=headers)
    paperDict = paperResponse.json()

    rowDict = {}
    institutionDict = {}

    # collect paper author names
    paperAuthorNames = []
    for authorship in paperDict["openalex_data"]["authorships"]:
        paperAuthorNames.append( authorship['author']['display_name'] )

    rowList.append( {'id': paperDict['openalex_id'], 'type': "Paper", 'title': paperDict['title'], 'doi': paperDict['doi'], 'authors': paperAuthorNames }  ) #change to authorIDs

    for authorship in paperDict["openalex_data"]["authorships"]:
        rowDict = authorship["author"]
        
        thisAuthorInstitutions = []
        #add all institutions for this author to rowList if they are not already there
        for institution in authorship["institutions"]:
            thisAuthorInstitutions.append(institution['display_name'])
            if institution["id"] not in institutionSet:
                institutionSet.add(institution["id"])
                rowList.append( {'id': institution['id'], 'type': "Institution", 'display_name': institution['display_name'] } )

        rowList.append( {'type': "Person"} | rowDict | {'institutions': thisAuthorInstitutions})

    return(rowList)


for paperURL in paperURLsList:
    getPaperAuthors(paperURL)



print(rowList)
#print(institutionSet)

############ write CSV file with: paper(title, doi, authors, institutions) ...(author-> orcid)
with open('paper_authors.csv', mode='w', newline='') as file:
    fieldnames = ['id', 'type', 'display_name', 'orcid', 'institutions', 'title', 'doi', 'authors']

    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()

    for row in rowList:
        writer.writerow(row)

# Print json data using loop
#for key in projectDict:{
#    print(key,":", projectDict[key])
#}

