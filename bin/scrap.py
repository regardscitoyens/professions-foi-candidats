#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, shutil
import re, time
import csv, json
import requests

HOSTURL = 'http://programme-candidats.interieur.gouv.fr'
DATAURL = HOSTURL + '/data-jsons/'

def downloadPDF(eldir, filename, url, retries=3):
    filepath = os.path.join(eldir, "%s.pdf" % filename)
    if os.path.exists(filepath):
        #print >> sys.stderr, "WARNING: already existing PDF", filepath
        return False
    try:
        r = requests.get(url, stream=True)
        r.raw.decode_content = True
        with open(filepath, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
        return True
    except Exception as e:
        if retries:
            time.sleep(2)
            return downloadPDF(eldir, filename, url, retries - 1)
        print >> sys.stderr, "WARNING: could not download %s for" % url, filename
        print >> sys.stderr, "%s:" % type(e), e
        return False

# deprecated
def collect_regionales(elcode="RG15"):
    eldir = os.path.join("documents", elcode)
    if not os.path.exists(eldir):
        os.makedirs(eldir)
    with open(os.path.join('res', 'listes.csv')) as f:
        listeIds = dict((row['nom'].strip().decode('utf-8'), row['couleur politique'].strip()) for row in list(csv.DictReader(f)))
    with open(os.path.join('res', 'regions.csv')) as f:
        regionIds = dict((row['region'].strip().decode('utf-8'), row['sigle'].strip()) for row in list(csv.DictReader(f)))
    for tour in [1, 2]:
        for region in request_data(DATAURL + 'elections-%s-regions' % tour, 'regions'):
            for liste in request_data(DATAURL + 'elections-%s-regions-%s-candidacies' % (tour, region['id']), 'lists'):
                regionId = regionIds[region['name']] if region['name'] in regionIds else region['name'].replace(' ', '_')
                listeId = listeIds[liste['name']] if liste['name'] in listeIds else liste['name'].replace(' ', '_')[:10]
                name = liste["principal"].split(',')[0].replace(' ', '_')
                codeId = '%s-%s-%s-%s-tour%s-' % (elcode, regionId, listeId, name, tour)
                if not liste['isBulletinDummy']:
                    downloadPDF(eldir, codeId + 'bulletin_vote', HOSTURL + liste['bulletinDeVote'])
                if not liste['isPropagandeDummy']:
                    downloadPDF(eldir, codeId + 'profession_foi', HOSTURL + liste['propagande'])

def request_data(url, field, retries=3):
    jsonurl = "%s.json" % url
    try:
        return requests.get(jsonurl).json()[field]
    except Exception as e:
        if retries:
            time.sleep(2)
            return request_data(url, field, retries - 1)
        print >> sys.stderr, "ERROR: impossible to get %s list at" % field, jsonurl
        print >> sys.stderr, "%s:" % type(e), e
        sys.exit(1)

re_election = re.compile(ur" 20(\d+)\s*-\s*(\d).*tour$")
def list_elections():
    elections = []
    for el in request_data(DATAURL + "elections", "elections"):
        eln = el["name"].lower()
        el[u"code"] = ""
        el[u"tour"] = 0
        el[u"granu"] = "departments"
        el[u"granu2"] = "circumscriptions"
        if u"présidentielle" in eln:
            typ = "PR"
        elif u"législative" in eln:
            typ = "LG"
        elif u"sénatoriale" in eln:
            typ = "SN"
        elif u"européenne" in eln:
            typ = "ER"
        elif u"régionale" in eln:
            typ = "RG"
            el["granu"] = "regions"
            el["granu2"] = "lists"
        elif u"départementale" in eln:
            typ = "DP"
        elif u"municipale" in eln:
            typ = "MN"
            el["granu2"] = "comunes"
        else:
            print >> sys.stderr, "WARNING: cannot identify type of election", el
            sys.exit(1)
        try:
            year, el["tour"] = re_election.search(eln).groups()
        except:
            print >> sys.stderr, "WARNING: cannot decode election", el
            sys.exit(1)
        el["code"] = typ + year
        elections.append(el)
    return elections

def scrape_election(el):
    eldir = os.path.join("documents", el["code"])
    if not os.path.exists(eldir):
        os.makedirs(eldir)
    nb_g = 0
    nb_g2 = 0
    nb_c = 0
    nb_d = 0
    nb_n = 0
    el[el["granu"]] = {}
    url = DATAURL + "elections-%s-%s" % (el["id"], el["granu"])
    for grain in request_data(url, el["granu"]):
        nb_g += 1
        grain[el["granu2"]] = {}
        el[el["granu"]][grain["id"]] = grain
        url1 = url + "-%s-%s" % (grain["id"], el["granu2"])
        for grain2 in request_data(url1, el["granu2"]):
            nb_g2 += 1
            url2 = url1 + "-%s-candidates" % grain2["id"]
            grain2["candidates"] = request_data(url2, "candidates")
            el[el["granu"]][grain["id"]][el["granu2"]][grain2["id"]] = grain2
            for candidate in grain2["candidates"]:
                nb_c += 1
                name = candidate["candidate"].split(',')[0].replace(' ', '_')
                codeId = '%s-%s-%s-%s-%s-tour%s-' % (el["code"], grain["id"], grain2["id"], name, candidate["order"], el["tour"])
                if not candidate['isPropagandeDummy']:
                    nb_d += 1
                    nb_n += downloadPDF(eldir, codeId + 'profession_foi', HOSTURL + candidate['propagande'])
                if "isBulletinDummy" in candidate and not candidate['isBulletinDummy']:
                    nb_n += downloadPDF(eldir, codeId + 'bulletin_vote', HOSTURL + candidate['bulletinDeVote'])

    with open(os.path.join(eldir, "%s-tour%s-metadata.json" % (el["code"], el["tour"])), "w") as f:
        json.dump(el, f, indent=2)
    if nb_n:
        print "%s: %s new documents collected (%s total candidates are published out of %s listed in %s %s and %s %s)." % (el["name"].encode("utf-8"), nb_n, nb_d, nb_c, nb_g, el["granu"], nb_g2, el["granu2"])

if __name__ == '__main__':
    election = ""
    if len(sys.argv) > 1:
        election = sys.argv[1]
    if election == "RG15":
        collect_regionales()
    else:
        for el in list_elections():
            if not election or election == el["code"]:
                scrape_election(el)
