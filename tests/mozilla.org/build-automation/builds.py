# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla Crash Automation Testing.
#
# The Initial Developer of the Original Code is
# Mozilla Corporation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
# Bob Clary
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import sys
from optparse import OptionParser
import os
import re
import couchquery
import urllib

sisyphus_dir     = os.environ["TEST_DIR"]
sys.path.append(os.path.join(sisyphus_dir,'bin'))

import sisyphus.couchdb

def ordered_ffversion(versionstring):
     versionstring = re.sub('[a-z].*$', '', versionstring)
     version = ''
     versionparts = re.split('[.]*', versionstring)
     for i in range(0,len(versionparts)):
         try:
             version += ( '00' +  versionparts[i] )[-2:]
         except:
             break # ignore and terminate

     return version

def main():

    usage = '''usage: %prog [options]

Initialize builds database at the specified couchdb server.

Example:
%prog --couch http://couchserver --versions 3.5:1.9.1,3.6:1.9.2,3.7:1.9.3


'''
    parser = OptionParser(usage=usage)
    parser.add_option('--couch', action='store', type='string',
                      dest='couchserveruri',
                      help='uri to couchdb server.')
    parser.add_option('--database', action='store', type='string',
                      dest='databasename',
                      help='name of database, defaults to sisyphus.',
                      default='sisyphus')
    parser.add_option('--versions', action='store', type='string',
                      dest='supported_versions',
                      default='3.5:1.9.1,3.6:1.9.2,3.7:1.9.3',
                      help='Comma delimited string of supported Firefox major versions:branches. ' +
                      'Defaults to 3.5:1.9.1,3.6:1.9.2,3.7:1.9.3')
    (options, args) = parser.parse_args()

    if options.couchserveruri is None:
         parser.print_help()
         exit(1)

    sisyphusdb = sisyphus.couchdb.Database(options.couchserveruri + '/' + options.databasename)

    sisyphusdb.sync_design_doc(os.path.join(os.path.dirname(sys.argv[0]), '_design'))

    branches_doc = {"_id" : "branches", "type" : "branches", "branches": [], "major_versions" : [], "version_to_branch": {}}
    versionsbranches    = options.supported_versions.split(',')
    for versionbranch in versionsbranches:
         version, branch = versionbranch.split(':')
         branches_doc["branches"].append(branch)
         branches_doc["major_versions"].append(ordered_ffversion(version))
         branches_doc["version_to_branch"][ordered_ffversion(version)] = branch

    branches_rows = sisyphusdb.getRows(sisyphusdb.db.views.builds.branches)

    if len(branches_rows) > 1:
        raise Exception("builds database has more than one branches document")

    if len(branches_rows) == 0:
        docinfo = sisyphusdb.createDocument(branches_doc)
        doc = sisyphusdb.getDocument("branches")
    else:
        doc = branches_rows[0]
        doc.branches = branches_doc["branches"]
        doc.version_to_branch = branches_doc["version_to_branch"]

    sisyphusdb.updateDocument(doc)

if __name__ == '__main__':
    main()
