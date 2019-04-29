#!/usr/bin/env python

import sys
import xml.etree.ElementTree as ET

if len(sys.argv) < 2 or not sys.argv[1]:
    print "usage: get-extension-uiid.py installrdfpath"
    sys.exit(1)

tree = ET.parse(sys.argv[1])
e  = tree.find("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description/{http://www.mozilla.org/2004/em-rdf#}id")
print  e.text
