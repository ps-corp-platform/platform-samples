# coding: utf-8
import requests
import re
import json
from datetime import datetime, date, timedelta
import config
import os
import csv
from collections import defaultdict, namedtuple

organizations = None
bad_users = []
good_users = []
all_users = []

GITHUB_API_URL = config.GITHUB_API_URL
GITHUB_API_TOKEN = config.GITHUB_API_TOKEN
DAYS_STOPPED = config.DAYS_STOPPED

HEADERS = {
    "Content-type": "application/json",
    "Authorization": "token {}".format(GITHUB_API_TOKEN)
}


def get_headers(org, tipo):
    # Obtem as páginas do header da requisiçao

    itens = []
    r = requests.get(url="{}/orgs/{}/{}".format(GITHUB_API_URL, org, tipo),
                     headers=HEADERS)
    res = r.headers
    reslink = res.get('Link')
    if reslink:
        pg = dict(NumberPG=int(re.search(r'e=([^>]*)>; rel="l',
                                         res['Link']).group(1)),
                  id=int(res['Link'].split('/')[4]))
        print(pg)
        itens.append(r.json())
        return pg, itens
    else:
        itens.append(r.json())
        return {"NumberPG": 1}, itens


def get_user_list(id, pg, users, org):
    # Obtem os usuários por páginas do PEOPLE da organização

    i = 1
    pg += 1

    for a in range(2, pg):
        i += 1
        users.append(requests.get(
            "{}/orgs/{}/members?page={}".format(GITHUB_API_URL, org, i),
            headers=HEADERS,
        ).json())

    return users


def get_user_activity(user):
    # Obtem os ultimos commits do user dentro da organização

    res = requests.get("{}/search/commits?q=author:{}&sort=author-date".format(
                GITHUB_API_URL, user),
                headers=dict(
                        **HEADERS,
                        Accept="application/vnd.github.cloak-preview"))

    if res.status_code == 200:
        content = json.loads(res.text)

        for event in content['items']:
            commit_org = event['repository']['owner']['login']
            if commit_org in organizations:
                return (
                    commit_org,
                    event['commit']['committer']['date']
                )

    return None, None


def get_users(org, limit_date):
    # Obtem as páginas do header da requisiçao

    pg, users = get_headers(org, 'members')

    if pg['NumberPG'] > 1:
        users = get_user_list(pg["id"], pg["NumberPG"], users, org)

    for listU in users:
        for u in listU:
            userExists = len(
                            list(
                                x for x in all_users
                                if(x['user'] == u['login'])
                            ))
            if not userExists:
                appendList(all_users, u['login'])
                commit_org, commit_date = get_user_activity(u['login'])

                if commit_org is not None:
                    commit_date = datetime.strptime(
                            commit_date.split('T')[0], '%Y-%m-%d'
                    ).date()

                    if commit_date < limit_date:
                        appendList(bad_users, u['login'], commit_date)
                    else:
                        appendList(good_users, u['login'], commit_date)
                else:
                    appendList(bad_users, u['login'], commit_date)


def appendList(listName, user, commit_date=None):
    # Adiciona o usuário a lista selecionada - Organização
    if commit_date:
        listName.append({
            'user': user,
            'commit-time': str(commit_date)
        })
    else:
        listName.append({
            'user': user
        })

def removeDuplicate():
    lines_seen = set() # holds lines already seen
    with open("../files/output_file.csv", "w") as output_file:
        for each_line in open("../files/unrecognized_authors.csv", "r"):
            if each_line not in lines_seen: # check if line is not duplicate
                output_file.write(each_line)
                lines_seen.add(each_line)
        os.rename("../files/output_file.csv", "../files/unrecognized_authors.csv")

def appendOrgs(name):
    # Gera os arquivos CSVs

    # Change /data/results
    out = {}
    tmpFile = "../files/tmp.csv"
    inputFile = f"../files/{name}.csv"

    with open(inputFile, "r") as f, open(tmpFile, "w", newline='') as outFile:
        reader = csv.reader(f)
        writer = csv.writer(outFile, delimiter=',')
        #writer.writerow(next(reader))
        for idt, txt in reader:
            temp = out.get(idt, "")
            out[idt] = temp+";"+txt if temp else txt
        writer.writerows(list(out.items()))
        os.rename(tmpFile, inputFile)

def compareFiles():
    with open('../files/all_users.csv', 'r') as t1, open('../files/inactive_users.csv', 'r') as t2:
        fileone = t1.readlines()
        filetwo = t2.readlines()

    with open('../files/result.csv', 'w') as outFile:
        for line in filetwo:
            if line in fileone:
                outFile.write(line)

if __name__ == "__main__":
    # CHange /data/orgs.json
    with open('orgs.json') as f:
        organizations = json.load(f)

    orgs = list(filter(lambda x: organizations[x] is True, organizations))

    for org in orgs:
        print(f"##### INICIANDO EXTRAÇÃO DE USUÁRIOS - {org} ######")
        os.environ['OCTOKIT_ACCESS_TOKEN'] = GITHUB_API_TOKEN
        os.environ['OCTOKIT_API_ENDPOINT'] = GITHUB_API_URL
        rvm_ruby = os.environ['OCTOKIT_ACCESS_TOKEN']
        execution = f"ruby find_inactive_members.rb -o {org} -d {DAYS_STOPPED}"
        os.system(execution)
    
    appendOrgs("all_users")
    appendOrgs("inactive_users")
    removeDuplicate()
    compareFiles()
