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

import os
import sys
import subprocess
import re

sisyphus_dir     = os.environ["TEST_DIR"]
sys.path.append(os.path.join(sisyphus_dir, 'bin'))

def buildProduct(db, product, branch, buildtype):
    buildsteps  = "checkout build"
    buildchangeset = None
    buildsuccess = True

    db.logMessage('begin building %s %s %s' % (product, branch, buildtype))

    proc = subprocess.Popen(
        [
            sisyphus_dir + "/bin/builder.sh",
            "-p", product,
            "-b", branch,
            "-T", buildtype,
            "-B", buildsteps
            ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True)

    stdout, stderr = proc.communicate()

    if re.search('^FATAL ERROR', stderr, re.MULTILINE):
        buildsuccess = False

    logs = stdout.split('\n')
    for logline in logs:
        logfilenamematch = re.search('log: (.*\.log)', logline)
        if logfilenamematch:
            logfilename = logfilenamematch.group(1)
            checkoutlogmatch = re.search('.*checkout.log', logfilename)
            if checkoutlogmatch:
                logfile = open(logfilename, 'rb')
                for line in logfile:
                    matchchangeset = re.search('build changeset:.* id (.*)', line)
                    if matchchangeset:
                        buildchangeset = matchchangeset.group(1)
                logfile.close()

            # only delete the log file if successful.
            if buildsuccess:
                os.unlink(logfilename)

    if buildsuccess:
        db.logMessage('success building %s %s %s changeset %s' % (product, branch, buildtype, buildchangeset))
    else:
        db.logMessage('failure building %s %s %s changeset %s' % (product, branch, buildtype, buildchangeset))

    return {"changeset" : buildchangeset, "success" : buildsuccess}

def clobberProduct(db, product, branch, buildtype):
    buildsteps  = "clobber"
    buildchangeset = None
    buildsuccess = True

    db.logMessage('begin clobbering %s %s %s' % (product, branch, buildtype))

    proc = subprocess.Popen(
        [
            sisyphus_dir + "/bin/builder.sh",
            "-p", product,
            "-b", branch,
            "-T", buildtype,
            "-B", buildsteps
            ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True)

    stdout, stderr = proc.communicate()

    if re.search('^FATAL ERROR', stderr, re.MULTILINE):
        buildsuccess = False

    logs = stdout.split('\n')
    for logline in logs:
        logfilenamematch = re.search('log: (.*\.log)', logline)
        if logfilenamematch:
            logfilename = logfilenamematch.group(1)
            # only delete the log file if successful.
            if buildsuccess:
                os.unlink(logfilename)

    if buildsuccess:
        db.logMessage('success clobbering %s %s %s' % (product, branch, buildtype))
    else:
        db.logMessage('failure clobbering %s %s %s' % (product, branch, buildtype))

    return buildsuccess

