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
import urllib

# http://simplejson.googlecode.com/svn/tags/simplejson-2.0.9/docs/index.html
try:
    import json
except:
    import simplejson as json

sisyphus_dir     = os.environ["TEST_DIR"]
tempdir          = os.path.join(sisyphus_dir, 'python')
if tempdir not in sys.path:
    sys.path.append(tempdir)

tempdir          = os.path.join(tempdir, 'sisyphus')
if tempdir not in sys.path:
    sys.path.append(tempdir)

tempdir          = os.path.join(tempdir, 'webapp')
if tempdir not in sys.path:
    sys.path.append(tempdir)

os.environ['DJANGO_SETTINGS_MODULE'] = 'sisyphus.webapp.settings'

import sisyphus.webapp.settings
from sisyphus.webapp.bughunter import models

def main():

    usage = '''usage: %prog [options]

Initialize unittest database.

Example:
%prog  [-t 'branch1:test1,test2+branch2:test1,test2,test3' | -j tests.json]

Initializes the database for the unittest framework.

The command line option -t can be used to specify the branches and the
corresponding tests which will be run on that branch. The option value
consists of a list of branch-test assignments delimited by the '+'
character. Each branch-test assignment begins with the branch followed
by ':' followed by a comma-delimited list of the test targets for the
branch. This option is most useful when the number of branches and
associated tests are small in number.

Example: -t 1.9.2:reftest+1.9.3:jstestbrowser,reftest

The command line option -j is used to specify a json file containing
the same information as the -t option but in a format that is easier
to use when the number of branches and tests are not small. The format
of the file must be valid json and be of the form:

{
  "branch1" :  [ "test1", "test2"],
  "branch2" :  [ "test1", "test2", "test3" ]
}

Example: -j tests.json

where tests.json contains:

{
  "2.0.0" :  [ "jstestbrowser", "reftest"]
}

It is an error if both -t and -j are specified. If neither is
specified, the default is equivalent to a tests.json file containing:

{
  "2.0.0" : ["reftest", "crashtest", "mochitest-plain", "mochitest-chrome", "jstestbrowser" ],
}
'''
    parser = OptionParser(usage=usage)

    parser.add_option('--tests', action='store', type='string',
                      dest='tests_dest',
                      default=None,
                      help='+ delimited string of branch-test assignments. ' +
                      'Defaults to None.')

    parser.add_option('--json', action='store', type='string',
                      dest='json_dest',
                      default=None,
                      help='file containing branch-test assignments in json format. ' +
                      'Defaults to None.')

    (options, args) = parser.parse_args()

    tests_by_branch = {}

    if options.json_dest and options.tests_dest:
         print "Only one of -j or -t may be specified."
         raise Exception("Usage")

    # restrict to 2.0.0 for now. note that reftest on 1.9.2 and lower
    # does not contain the fix for
    # https://bugzilla.mozilla.org/show_bug.cgi?id=523934 to disable
    # slow script dialogs which makes running reftest, crashtest or
    # jstestbrowser problematic there.

    if options.tests_dest:

        branchdatalist = options.tests_dest.split('+')
        for branchdataitem in branchdatalist:
            branchdata = branchdataitem.split(':')
            branch     = branchdata[0]
            testlist   = branchdata[1].split(',')
            tests_by_branch[branch] = testlist

    elif options.json_dest:

        jsonfilehandle  = open(options.json_dest, "r")
        jsonstring      = jsonfilehandle.read(-1)
        jsonfilehandle.close()
        tests_by_branch = json.loads(jsonstring)

    else:

        tests_by_branch = {
            "2.0.0" : ["reftest", "crashtest", "jstestbrowser", "mochitest-plain", "mochitest-chrome"]
            }

    testbranch_rows = models.UnitTestBranch.objects.all()

    # remove previous branch-test mapping
    for testbranch_row in testbranch_rows:
        testbranch_row.delete()

    for branch in tests_by_branch:
        for test in tests_by_branch[branch]:
            testbranch_row = models.UnitTestBranch(branch = branch, test = test)
            testbranch_row.save()

if __name__ == '__main__':
    main()
