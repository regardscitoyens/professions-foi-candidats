#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, shutil
import re, time
import csv, json
import requests

HOSTURL = 'https://programme-candidats.interieur.gouv.fr/'
DATAURL = HOSTURL + 'data-jsons/'
DATAURL2 = HOSTURL + 'ajax/data/'
PDFSURL = HOSTURL + "data-pdf-propagandes/"

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

def request_data(url, field, fallback_field=None, retries=10):
    jsonurl = "%s.json?_=%s" % (url, time.time())
    try:
        jsondata = requests.get(jsonurl).json()
        if field in jsondata:
            return jsondata[field]
        return jsondata[fallback_field]
    except Exception as e:
        if retries:
            time.sleep(30/retries)
            return request_data(url, field, fallback_field=fallback_field, retries = retries - 1)
        print >> sys.stderr, "ERROR: impossible to get %s list at" % field, jsonurl
        print >> sys.stderr, "%s:" % type(e), e
        sys.exit(1)

re_election = re.compile(ur" 20(\d+)(?:\s*-\s*(\d).*tour)?$")
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
        elif u"européen" in eln:
            typ = "ER"
            el["granu"] = "candidacies"
            el["granu2"] = "lists"
        elif u"régionale" in eln:
            typ = "RG"
            el["granu"] = "regions"
            el["granu2"] = "lists"
        elif u"départementale" in eln:
            typ = "DP"
        elif u"municipale" in eln:
            typ = "MN"
            el["granu2"] = "communes"
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
    tour = "-tour%s" % el["tour"] if el["tour"] else ""
    url = DATAURL + "elections-%s-%s" % (el["id"], el["granu"])
    for grain in request_data(url, el["granu"], el["granu2"]):
        nb_g += 1
        if "propagande" in grain:
            if "listes" not in el:
                el["listes"] = []
            el["listes"].append(grain)
            nb_c += 1
            name = re.sub(r'[^A-ZÀÂÉÊÈÎÏÔÙÛÇ]+', '_', grain['name'])
            codeId = '%s-%s-%s-' % (el["code"], name, grain["order"])
            if not int(grain['isPropagandeDummy']):
                nb_d += 1
                nb_n += downloadPDF(eldir, codeId + 'profession_foi', HOSTURL + grain['propagande'])
            if not int(grain['isFalcDummy']):
                nb_n += downloadPDF(eldir, codeId + 'profession_foi_accessible', HOSTURL + grain['accessible_propagande'])
        else:
            graindir = os.path.join(eldir, grain["id"])
            if not os.path.exists(graindir):
                os.makedirs(graindir)
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
                    codeId = '%s-%s-%s-%s-%s%s-' % (el["code"], grain["id"], grain2["id"], name, candidate["order"], tour)
                    if not int(candidate['isPropagandeDummy']):
                        nb_d += 1
                        nb_n += downloadPDF(graindir, codeId + 'profession_foi', HOSTURL + candidate['propagande'])
                    if "isBulletinDummy" in candidate and not int(candidate['isBulletinDummy']):
                        nb_n += downloadPDF(graindir, codeId + 'bulletin_vote', HOSTURL + candidate['bulletinDeVote'])

    with open(os.path.join(eldir, "%s%s-metadata.json" % (el["code"], tour)), "w") as f:
        json.dump(el, f, indent=2)
    if nb_n:
        print "%s: %s new documents collected (%s total candidates are published out of %s listed in %s %s and %s %s)." % (el["name"].encode("utf-8"), nb_n, nb_d, nb_c, nb_g, el["granu"], nb_g2, el["granu2"])


def scrape_municipales(elcode="MN20"):
    eldir = os.path.join("documents", elcode)
    if not os.path.exists(eldir):
        os.makedirs(eldir)
    nb_dep = 0
    nb_com = 0
    nb_c = 0
    nb_d = 0
    nb_n = 0
    url = DATAURL2 + "departements"
    data = {}
    for dept in request_data(url, "departements"):
        nb_dep += 1
        depcode = dept["id"]
        depname = dept["name"]
        depurl = DATAURL2 + "communes_%s" % depcode
        data[depcode] = {
            "name": depname,
            "url": depurl,
            "communes": {}
        }
        deptdir = os.path.join(eldir, depcode)
        if not os.path.exists(deptdir):
            os.makedirs(deptdir)
        for commune in request_data(depurl, "data"):
            nb_com += 1
            comcode = commune["id"]
            comname = commune["name"]
            comurl = DATAURL2 + "candidats_%s" % comcode
            data[depcode]["communes"][comcode] = {
                "name": comname,
                "url": comurl,
                "candidats": request_data(comurl, "data")
            }
            comdir = os.path.join(deptdir, comcode)
            if not os.path.exists(comdir):
                os.makedirs(comdir)
            for candidat in data[depcode]["communes"][comcode]["candidats"]:
                nb_c += 1
                name = candidat["candidat"].split(',')[0].replace(' ', '_')
                codeId = '%s-%s-%s-%s-%s%s-' % (elcode, depcode, comcode, name, candidat["num"], "2")
                if candidat['pdf'] != "0":
                    nb_d += 1
                    nb_n += downloadPDF(comdir, codeId + 'profession_foi', PDFSURL + "%s.pdf" % candidat['pdf'])

    with open(os.path.join(eldir, "%s%s-metadata.json" % (elcode, "2")), "w") as f:
        json.dump(data, f, indent=2)
    if nb_n:
        print "%s: %s new documents collected (%s total candidates are published out of %s listed in %s departments and %s communes)." % (elcode, nb_n, nb_d, nb_c, nb_dep, nb_com)


if __name__ == '__main__':
    election = ""
    if len(sys.argv) > 1:
        election = sys.argv[1]
    if election == "RG15":
        collect_regionales()
    elif election == "MN20":
        scrape_municipales()
    else:
        for el in list_elections():
            if not election or election == el["code"]:
                scrape_election(el)
