# coding: utf-8
import requests
import re
import json
from datetime import datetime, date, timedelta
import config
import csv


for org in {"ps-rewards","ps-wallet"}; do ruby find_inactive_members.rb -o ${org} -d "Dec 23 2020"; done

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


def printFileCSV(name, lista, tipo):
    # Gera os arquivos CSVs

    campos = {
            'commit': ['user', 'commit-time'],
            'all': ['user'],
    }

    # Change /data/results
    write_obj = open(f"/data/results/{name}.csv", 'w', newline='')
    dict_writer = csv.DictWriter(write_obj, fieldnames=campos[tipo])
    dict_writer.writeheader()

    for item in lista:
        dict_writer.writerow(item)


if __name__ == "__main__":
    # CHange /data/orgs.json
    with open('orgs.json') as f:
        organizations = json.load(f)

    limit_date = date.today() - timedelta(days=DAYS_STOPPED)
    orgs = list(filter(lambda x: organizations[x] is True, organizations))

    for org in orgs:
        print(f"##### INICIANDO EXTRAÇÃO DE USUÁRIOS - {org} ######")
        get_users(org, limit_date)

    printFileCSV("bad_users", bad_users, 'commit')
    printFileCSV("good_users", good_users, 'commit')
    printFileCSV("all_users", all_users, 'all')
