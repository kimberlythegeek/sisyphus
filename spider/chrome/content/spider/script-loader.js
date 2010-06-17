/* -*- Mode: C++; tab-width: 8; indent-tabs-mode: nil; c-basic-offset: 4 -*- */
/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is Mozilla Spider Code.
 *
 * The Initial Developer of the Original Code is
 * Mozilla Corporation.
 * Portions created by the Initial Developer are Copyright (C) 2006
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s): Bob Clary <bob@bclary.com>
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 *
 * ***** END LICENSE BLOCK ***** */

/**
 * loadScript
 *
 * Synchronously loads a script specified by the url aScriptUrl
 * and evaluates it in the scope of the window object.
 *
 * loadScript will be aborted if the script has not loaded in
 * loadScript.timeout milliseconds. Note that the script is loaded
 * synchronously and will block the browser until it completes or
 * times out.
 *
 * The script url, source and XMLHttpRequest object for the last
 * invocation are available in :
 * loadScript.scripturl
 * loadScript.source
 * loadScript.xmlhttp
 */

function loadScript(aScriptUrl)
{
    dlog('loadScript: aScriptUrl:  ' + aScriptUrl);

    loadScriptXHR(aScriptUrl);
}

function loadScriptXHR(aScriptUrl)
{
    dlog('loadScriptXHR: aScriptUrl:  ' + aScriptUrl);

    loadScriptXHR.scripturl = aScriptUrl;
    loadScriptXHR.source    = '';

    loadScriptXHR.xmlhttp = new XMLHttpRequest();
    loadScriptXHR.xmlhttp.overrideMimeType('text/plain');
    loadScriptXHR.xmlhttp.open('GET', aScriptUrl, false);
    loadScriptXHR.watcherid = setTimeout(watchLoadScriptXHR, loadScriptXHR.timeout);
    loadScriptXHR.xmlhttp.send(null);

    if (/^OK/i.test(loadScriptXHR.xmlhttp.statusText))
    {
        // deal with non-standard OK responses...
        clearTimeout(loadScriptXHR.watcherid);
        loadScriptXHR.watcherid = null;
        loadScriptXHR.source = loadScriptXHR.xmlhttp.responseText;

        try
        {
            dlog('loadScriptXHR: eval(...): aScope undefined. this: ' + this + ', window: ' + window);
            window.eval(loadScriptXHR.source);
            return;
        }
        catch(ex)
        {
            dlog('loadScriptXHR(' + loadScriptXHR.scripturl + ') failed to eval script ' +
                  ex + ' ' +
                  loadScriptXHR.xmlhttp.statusText);
        }

        if ('location' in window && 'href' in window.location)
        {
            // if the scope object is a window or document with a location
            // object, evaluate the script in the context of the scope
            // by injecting a javascript: url to overcome cross domain
            // eval alias issues.
            try
            {
                dlog('loadScriptXHR: using javascript:');
                window.location.href = 'javascript:' + encodeURIComponent(loadScriptXHR.source) + ';void(0);';
                return;
            }
            catch(ex)
            {
                cdump('loadScriptXHR(' + loadScriptXHR.scripturl + ') failed to inject script ' +
                      ex + ' ' +
                      loadScriptXHR.xmlhttp.statusText);
            }
        }
    }
}

function watchLoadScriptXHR()
{
    try
    {
        loadScriptXHR.xmlhttp.abort();
        cdump('loadScriptXHR(' + loadScriptXHR.scripturl +
              '): Timed out (' +
              (loadScriptXHR.timeout/1000) +
              ' seconds)');
    }
    catch(ex)
    {
        cdump('watchLoadScriptXHR: ' + ex);
    }
}

loadScriptXHR.timeout = 120000;
