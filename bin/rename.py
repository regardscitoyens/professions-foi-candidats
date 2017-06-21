#!/usr/bin/env python
# -*- coding: utf8 -*-

import os
import re
import sys

folder = sys.argv[1]
filename_splitter = re.compile(r"(.*)-(\d+|\d[AB])-(\d+)-(.*)-(\d+)-tour(\d)-(.*)")

for root, dirs, files in os.walk(folder):
	for file in files:
		path = os.path.join(root, file)
		if path[-3:] == "pdf":
			filename_splitted = filename_splitter.search(file[2:-4])
			year, dept, circo, nom, ordre, tour, typedoc = filename_splitted.groups()
		
			cote = "ELWWW"
			election = "L"
			year = "20" + year
			month = "06"
			dept = dept.zfill(3)
			circo = circo.zfill(2)
			tour = tour[-1:]
			typedoc = "PF"

			new_filename = '_'.join([cote, election, year, month, dept, circo, tour, typedoc, nom]) + ".pdf"
			new_path = os.path.join(root, new_filename)
			
			os.rename(path, new_path)


