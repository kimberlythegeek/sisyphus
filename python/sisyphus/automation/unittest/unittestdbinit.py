# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from optparse import OptionParser
import json
import os
import re
import sys
import urllib

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
  "nightly" :  [ "jstestbrowser", "reftest"]
}

It is an error if both -t and -j are specified. If neither is
specified, the default is equivalent to a tests.json file containing:

{
  "nightly" : ["reftest", "crashtest", "mochitest-plain", "mochitest-chrome", "jstestbrowser" ],
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
            "nightly" : ["reftest", "crashtest", "jstestbrowser", "mochitest-plain", "mochitest-chrome"]
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
