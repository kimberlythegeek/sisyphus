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
# Jesse Ruderman
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

import traceback
import datetime
import re
import signal
import os

def makeUnicodeString(s):
    # http://farmdev.com/talks/unicode/
    if isinstance(s, basestring):
        if not isinstance(s, unicode):
            s = unicode(s, "utf-8", errors='replace')
    return s

def formatException(etype, evalue, etraceback):
    return str(traceback.format_exception(etype, evalue, etraceback))

def getTimestamp(hiresolution=False):
    timestamp = datetime.datetime.now()
    datetimestamp = datetime.datetime.strftime(timestamp, "%Y-%m-%dT%H:%M:%S")
    if hiresolution:
        datetimestamp = "%s.%06d" % (datetimestamp, timestamp.microsecond)
    return datetimestamp

def convertTimestamp(s):
    try:
        s = re.sub('\.[0-9]*$', '', s)
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except KeyboardInterrupt:
        raise
    except:
        pass

    return datetime.datetime.strptime('2009-01-1T00:00:00', "%Y-%m-%dT%H:%M:%S")

def convertTimeToString(timestamp, hiresolution=False):
    datetimestamp = datetime.datetime.strftime(timestamp, "%Y-%m-%dT%H:%M:%S")
    if hiresolution:
        datetimestamp = "%s.%06d" % (datetimestamp, timestamp.microsecond)
    return datetimestamp

# getSignalName cribbed from timed_run.py by Jesse Ruderman
def getSignalName(num):
    for p in dir(signal):
        if p.startswith("SIG") and not p.startswith("SIG_"):
            if getattr(signal, p) == num:
                return p
    return "UNKNOWN"

def convertReturnCodeToExitStatusMessage(rc):
    exitstatusmessage = ""

    if not isinstance(rc, int):
        exitstatusmessage = "None"

    elif os.WIFSIGNALED(rc):
        signum = os.WTERMSIG(rc)
        exitstatusmessage = "signal %d %s" % (signum, getSignalName(signum))

    elif os.WIFEXITED(rc):
        exitstatus = os.WEXITSTATUS(rc)
        if exitstatus == 0:
            exitstatusmessage = 'NORMAL'
        else:
            exitstatusmessage = 'ABNORMAL ' + str(exitstatus)

    if isinstance(rc, int) and os.WCOREDUMP(rc):
        exitstatusmessage += " dumped core"

    return exitstatusmessage.strip()

def timedReadLine_handler(signum, frame):
    print 'timedReadLine timeout'
    raise IOError('ReadLineTimeout')

def timedReadLine(filehandle, timeout = 300):
    """
    Attempt to readline from filehandle. If readline does not return
    within timeout seconds, return an empty line.
    """

    signal.signal(signal.SIGALRM, timedReadLine_handler)
    signal.alarm(timeout)

    try:
        line = filehandle.readline()
    except:
        line = ''

    signal.alarm(0)

    return line
