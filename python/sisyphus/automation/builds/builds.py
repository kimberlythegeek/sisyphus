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
from sisyphus.webapp.bughunter.models import Branch

def ordered_ffversion(versionstring):
    versionstring = re.sub('[a-z].*$', '', versionstring)
    version = ''
    versionparts = re.split('[.]*', versionstring)
    for i in range(0,len(versionparts)):
        try:
            version += ( '00' +  versionparts[i] )[-2:]
        except KeyboardInterrupt, SystemExit:
            raise
        except:
            break # ignore and terminate

    return version

def main():

    usage = '''usage: %prog [options]

Initialize branch table mapping branches to major versions for the product.

Example:
%prog --product firefox --versions 4.0:2.0.0,5.0:beta,6.0:aurora,7.0:nightly


'''
    parser = OptionParser(usage=usage)

    parser.add_option('--product', action='store', type='string',
                      dest='product',
                      help='name of product, defaults to firefox.',
                      default='firefox')

    parser.add_option('--versions', action='store', type='string',
                      dest='supported_versions',
                      default='4.0:2.0.0,5.0:beta,6.0:aurora,7.0:nightly',
                      help='Comma delimited string of supported Firefox major versions:branches. ' +
                      'Defaults to 4.0:2.0.0,5.0:beta,6.0:aurora,7.0:nightly')

    parser.add_option('--buildtypes', action='store', type='string',
                      dest='buildtypes',
                      help='comma delimited string containing build types: opt, debug. Defaults to debug.',
                      default='debug')

    (options, args) = parser.parse_args()

    # replace all rows in the Branch table
    Branch.objects.all().delete()

    versionsbranches    = options.supported_versions.split(',')
    buildtypes          = options.buildtypes.split(',')

    for versionbranch in versionsbranches:
        version, branch = versionbranch.split(':')
        for buildtype in buildtypes:
            branch_row = Branch(product       = options.product,
                                branch        = branch,
                                major_version = ordered_ffversion(version),
                                buildtype     = buildtype)
            branch_row.save()

if __name__ == '__main__':
    main()
