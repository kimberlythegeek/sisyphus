# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

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
