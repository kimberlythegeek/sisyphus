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

# http://code.google.com/p/httplib2/
import httplib2

# http://simplejson.googlecode.com/svn/tags/simplejson-2.0.9/docs/index.html
try:
    import json
except:
    import simplejson as json

import signal
import sys
import re
import time
import urllib

bzapiurl = 'https://api-dev.bugzilla.mozilla.org/latest/'

def timedHttpRequest_handler(signum, frame):
    print 'timedHttpRequest timeout'
    raise IOError('HttpRequestTimeout')

def timedHttpRequest(url, timeout = 300):
    """
    Attempt to perform an http request. If it does not return within
    timeout seconds, raise an empty response. Retry once after a delay
    of 1 minute if the http request throws an exception.

    usage: resp, content = timedHttpRequest('http://example.com/?yomama', 300)

    """
    for attempt in range(2):
        try:
            signal.signal(signal.SIGALRM, timedHttpRequest_handler)

            http = httplib2.Http()
            signal.alarm(timeout)
            resp, content = http.request(url)
            signal.alarm(0)

        except:
            signal.alarm(0)
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionType != IOError and not re.search('/httplib2/', str(exceptionValue)):
                raise
            resp = {}
            content = '{}'
            time.sleep(60)

    try:
        jcontent = json.loads(content)
    except:
        jcontent = {}

    return resp, jcontent

def searchBugzillaSummary(query, querytype='contains'):
    """
    Search bugzilla using the bugzilla rest api for bugs containing
    the string query in summary returning the response and content
    as a json 2-tuple.

    usage: resp, content = searchBugzillaSummary('yomama')

    """
    resp, content = timedHttpRequest(bzapiurl + "bug?summary_type=" + querytype + "&summary=" + urllib.quote(query))
    return resp, content

def searchBugzillaComments(query, querytype='contains'):
    """
    Search bugzilla using the bugzilla rest api for bugs containing
    the string query in the comments returning the response and content
    as a json 2-tuple.

    usage: resp, content = searchBugzillaComments('yomama')

    """
    resp, content = timedHttpRequest(bzapiurl +
                                 "bug?comment_type=" + querytype + "&comment=" + urllib.quote(query))
    return resp, content

def searchBugzillaText(query, querytype='contains'):
    """
    Search bugzilla using the bugzilla rest api for bugs containing
    the string query in either the summary or comments returning the
    response and content as a json 2-tuple.

    usage: resp, content = searchBugzillaText('yomama')

    """

    query = urllib.quote(query)
    resp, content = timedHttpRequest(bzapiurl +
                                 "bug?field0-0-0=summary&type0-0-0=" + querytype + "&value0-0-0=" + query +
                                 "&field0-0-1=comment&type0-0-1=" + querytype + "&value0-0-1=" + query)

    return resp, content

if __name__ == "__main__":
    """
    Tests which run when the script is executed rather than imported.
    Usage: python bugzilla.py
    """
    print "searchBugzillaSummary"
    resp, content = searchBugzillaSummary("Wrong scope, this is really bad!: 'JS_GetGlobalForObject(cx, obj) == newScope'")
    print "resp: %s" % json.dumps(resp)
    print "content: %s" % json.dumps(content)

    print "searchBugzillaComments"
    resp, content = searchBugzillaComments("Wrong scope, this is really bad!: 'JS_GetGlobalForObject(cx, obj) == newScope'")
    print "resp: %s" % json.dumps(resp)
    print "content: %s" % json.dumps(content)

    print "searchBugzillaText"
    resp, content = searchBugzillaText("Wrong scope, this is really bad!: 'JS_GetGlobalForObject(cx, obj) == newScope'")
    print "resp: %s" % json.dumps(resp)
    print "content: %s" % json.dumps(content)


