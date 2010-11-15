/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */
/*-- ***** BEGIN LICENSE BLOCK *****
  - Version: MPL 1.1/GPL 2.0/LGPL 2.1
  -
  - The contents of this file are subject to the Mozilla Public License Version
  - 1.1 (the "License"); you may not use this file except in compliance with
  - the License. You may obtain a copy of the License at
  - http://www.mozilla.org/MPL/
  -
  - Software distributed under the License is distributed on an "AS IS" basis,
  - WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
  - for the specific language governing rights and limitations under the
  - License.
  -
  - The Original Code is Netscape Code.
  -
  - The Initial Developer of the Original Code is
  - Netscape Corporation.
  - Portions created by the Initial Developer are Copyright (C) 2003
  - the Initial Developer. All Rights Reserved.
  -
  - Contributor(s): Bob Clary <bclary@netscape.com>
  -                 Bob Clary <http://bclary.com/>
  -
  - Alternatively, the contents of this file may be used under the terms of
  - either the GNU General Public License Version 2 or later (the "GPL"), or
  - the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
  - in which case the provisions of the GPL or the LGPL are applicable instead
  - of those above. If you wish to allow use of your version of this file only
  - under the terms of either the GPL or the LGPL, and not to allow others to
  - use your version of this file under the terms of the MPL, indicate your
  - decision by deleting the provisions above and replace them with the notice
  - and other provisions required by the LGPL or the GPL. If you do not delete
  - the provisions above, a recipient may use your version of this file under
  - the terms of any one of the MPL, the GPL or the LGPL.
  -
  - ***** END LICENSE BLOCK ***** */

function loadHandler(evt)
{
  try
  {
    dlog('loadHandler: timeStamp=' + evt.timeStamp +
         ', bubbles=' + evt.bubbles +
         ', currentTarget=' + evt.currentTarget +
         ', eventPhase=' + evt.eventPhase +
         ', target=' + evt.target +
         ', originalTarget=' + evt.originalTarget +
         ', type=' + evt.type);
  }
  catch(ex)
  {
    dlog('loadHandler: ' + ex + '');
  }
}

this.addEventListener('load', loadHandler, true);

var gOutput;
var gSpider;
var gHelp;
var gForm;
var gPageLoader;
var gRestartThread = 0;
var gPauseState = '';
var gWaitTime = 0;
var xhtmlns = 'http://www.w3.org/1999/xhtml';

// for page transition logic
var gPageCompleted = false;

function init(evt, querystring)
{
  dlog('init: timeStamp=' + evt.timeStamp +
       ', bubbles=' + evt.bubbles +
       ', currentTarget=' + evt.currentTarget +
       ', eventPhase=' + evt.eventPhase +
       ', target=' + evt.target +
       ', originalTarget=' +
       ', type=' + evt.type);

  if (Event.AT_TARGET != evt.eventPhase)
  {
    // work around https://bugzilla.mozilla.org/show_bug.cgi?id=196057
    return;
  }

  // required since remote xul doesn't set the title
  // from the window title?
  if (!document.title)
  {
    document.title = 'Spider';
  }

  sayVersion();

  if (window.opener)
  {
    try
    {
      window.opener.close();
    }
    catch(e)
    {
    }
  }

  gPageLoader = new CPageLoader();
  gForm = document.getElementById('spiderForm');

  if ('arguments' in window && typeof window.arguments != 'undefined')
  {
    // arguments passed via the commandline handler
    var oArguments = eval(window.arguments[0]);

    if (oArguments.uri != null)
      gForm.url.value          = oArguments.uri;
    else
      gForm.url.value          = oArguments.url;

    gForm.domain.value       = oArguments.domain;
    gForm.restrict.checked   = (oArguments.domain != null);
    gForm.depth.value        = oArguments.depth;
    gForm.timeout.value      = oArguments.timeout;
    gForm.waittime.value     = oArguments.wait;
    gForm.hooksignal.checked = (oArguments.hook != null);
    gForm.autostart.checked  = (oArguments.start == true);
    gForm.autoquit.checked   = (oArguments.quit == true);
    gForm.respectrobotrules.checked = (oArguments.robot == true);
    gForm.debug.checked      = (oArguments.debug == true);
    gForm.javascripterrors.checked  = (oArguments.jserrors == true);
    gForm.javascriptwarnings.checked  = (oArguments.jswarnings == true);
    gForm.chromeerrors.checked  = (oArguments.chromeerrors == true);
    gForm.xblerrors.checked  = (oArguments.xblerrors == true);
    gForm.csserrors.checked  = (oArguments.csserrors == true);
    gForm.httpresponses.checked  = (oArguments.httpresponses == true);
    gForm.scripturl.value = oArguments.hook;

  }
  else if (querystring)
  {
    FormInit(gForm, querystring);
    // the url needs to be double encoded to be run from the command
    // line. decode a second time.
    gForm.url.value = decodeURIComponent(gForm.url.value);
  }

  gDebug = gForm.debug.checked;
  dlog('init: querystring ' + querystring);

  registerConsoleListener();

  if (gForm.autostart.checked)
  {
    setTimeout('main(gForm)', 100);
  }
}

function updateScriptUrlStatus(s)
{
  var scripturlstatus = document.getElementById('scripturlstatus');
  while (scripturlstatus.firstChild)
  {
    scripturlstatus.removeChild(scripturlstatus.firstChild);
  }
  scripturlstatus.appendChild(document.createTextNode(s));
}

function main(form)
{
  if (!gOutput)
  {
    gOutput = document.getElementById('output');
  }

  if (!gInChrome && gCanHaveChromePermissions)
  {
    try
    {
      netscape.security.PrivilegeManager.
        enablePrivilege(gConsoleSecurityPrivileges);
    }
    catch(e)
    {
      msg(e);
      return;
    }
  }

  var url = gForm.url.value;
  var domain = gForm.domain.value;
  var depth = parseInt(gForm.depth.value);
  var restrict = gForm.restrict.checked;
  var timeout = parseFloat(gForm.timeout.value);
  var respectrobotrules = gForm.respectrobotrules.checked;
  gWaitTime = parseFloat(gForm.waittime.value) * 1000;
  gDebug = gForm.debug.checked;

  gConsoleListener.javascriptErrors   = gForm.javascripterrors.checked;
  gConsoleListener.javascriptWarnings = gForm.javascriptwarnings.checked;
  gConsoleListener.cssErrors          = gForm.csserrors.checked;
  gConsoleListener.httpResponses      = gForm.httpresponses.checked;
  gConsoleListener.chromeErrors       = gForm.chromeerrors.checked;
  gConsoleListener.xblErrors          = gForm.xblerrors.checked;

  if (gForm.scripturl.value)
  {
    var scripturl = gForm.scripturl.value.replace(/[ \t]/g, '');
    var excp;
    var excpmsg;
    try
    {
      loadScript(scripturl);
      updateScriptUrlStatus('Compile Successful');
    }
    catch(excp)
    {
      excpmsg = 'Compile Failed ' + ' ' + excp + ' ' + excp.stack;
      dlog(excpmsg);
      updateScriptUrlStatus(excpmsg);
      throw(excp);
    }
  }

  // invoke with extra privileges even though chrome xul doesn't require
  // them. this should allow remote xul to work cross domain.

  gSpider = new CSpider(url, domain, restrict, depth, gPageLoader, timeout,
                        true, respectrobotrules);

  // CSpider is a strategy pattern. You customize its
  // behavior by specifying the following functions which
  // will be called by CSpider on your behalf.

  gSpider.mOnStart = function CSpider_mOnStart()
    {
      dlog('CSpider.mOnStart()');
      msg('starting...');

      cdump('Spider: Start: ' +
            (gForm.url.value                  ? '-url "'    + gForm.url.value       + '" '  : '') +
            (gForm.scripturl.value            ? '-hook "'   + gForm.scripturl.value + '" '  : '') +
            (gForm.domain.value               ? '-domain "' + gForm.domain.value    + '" '  : '') +
            (gForm.depth.value                ? '-depth '   + gForm.depth.value     + ' '   : '') +
            (gForm.timeout.value              ? '-timeout ' + gForm.timeout.value   + ' '   : '') +
            (gForm.waittime.value             ? '-wait '    + gForm.waittime.value  + ' '   : '') +
            (gForm.autostart.checked          ? '-start '                                   : '') +
            (gForm.autoquit.checked           ? '-quit '                                    : '') +
            (gForm.respectrobotrules.checked  ? '-robot '                                   : '') +
            (gForm.debug.checked              ? '-debug '                                   : '') +
            (gForm.javascripterrors.checked   ? '-jserrors '                                : '') +
            (gForm.javascriptwarnings.checked ? '-jswarnings '                              : '') +
            (gForm.chromeerrors.checked       ? '-chromeerrors '                            : '') +
            (gForm.xblerrors.checked          ? '-xblerrors '                               : '') +
            (gForm.csserrors.checked          ? '-csserrors '                               : '') +
            (gForm.httpresponses.checked      ? '-httpresponses '                           : '')
        );

      if (!gInChrome && gCanHaveChromePermissions)
      {
        var e;
        try
        {
          netscape.security.PrivilegeManager.
            enablePrivilege(gConsoleSecurityPrivileges);
        }
        catch(e)
        {
          msg(e);
          return false;
        }
      }

      gForm.run.disabled = true;
      gForm.save.disabled = true;
      gForm.reset.disabled = true;
      gForm.pause.disabled = false;
      gForm.restart.disabled = true;
      gForm.stop.disabled = false;

      if (typeof(userOnStart) == 'function')
      {
        try
        {
          userOnStart();
        }
        catch(e)
        {
          var errmsg = 'Error: userOnStart User Hook ' + e;
          updateScriptUrlStatus(errmsg);
          cdump('Spider: ' + errmsg);
        }
      }

      return true;
    };

  gSpider.mOnBeforePage = function CSpider_mOnBeforePage()
    {
      dlog('CSpider.mOnBeforePage()');

      gPageCompleted = false;

      msg('Loading      : ' +  this.mCurrentUrl.mUrl +  '\n' +
          'Depth        : ' + this.mCurrentUrl.mDepth + '\n' +
          'Remaining    : ' + this.mPagesPending.length + '\n' +
          'Total loaded : ' + this.mPagesVisited.length);

      cdump('Spider: Begin loading ' + this.mCurrentUrl.mUrl);

      if (!gInChrome && gCanHaveChromePermissions)
      {
        var e;
        try
        {
          netscape.security.PrivilegeManager.
            enablePrivilege(gConsoleSecurityPrivileges);
        }
        catch(e)
        {
          msg(e);
          return false;
        }
      }

      if (typeof(userOnBeforePage) == 'function')
      {
        try
        {
          userOnBeforePage();
        }
        catch(e)
        {
          var errmsg = 'Error: userOnBeforePage User Hook ' + e;
          updateScriptUrlStatus(errmsg);
          cdump('Spider: ' + errmsg);
        }
      }

      return true;
    };

  gSpider.mOnAfterPage = function CSpider_mOnAfterPage()
    {
      dlog('CSpider.mOnAfterPage()');

      msg('Page loaded: ' + this.mCurrentUrl.mUrl + '\n' +
          'Depth        : ' + this.mCurrentUrl.mDepth + '\n' +
          'Remaining    : ' + this.mPagesPending.length + '\n' +
          'Total loaded : ' + this.mPagesVisited.length);

      cdump('Spider: Finish loading ' + this.mCurrentUrl.mUrl);

      cdump('Spider: Current Url: ' + this.mCurrentUrl.mUrl +
            ', Referer: ' + this.mCurrentUrl.mReferer +
            ', Depth: ' + this.mCurrentUrl.mDepth);
      if (gConsoleListener.httpResponses)
      {
        var responses = this.mCurrentUrl.mResponses;
        for (var iResponse = 0; iResponse < responses.length; iResponse++)
        {
          var response = responses[iResponse];
          cdump('Spider: HTTP Response:' +
                ' originalURI: ' + response.originalURI +
                ' URI: ' + response.URI +
                ' referer: ' + response.referrer +
                ' status: ' + response.responseStatus +
                ' status text: ' + response.responseStatusText +
                ' content-type: ' + response.contentType +
                ' succeeded: ' + response.requestSucceeded);
        }
      }

      if (!gInChrome && gCanHaveChromePermissions)
      {
        try
        {
          netscape.security.PrivilegeManager.
          enablePrivilege(gConsoleSecurityPrivileges);
        }
        catch(e)
        {
          msg(gConsoleSecurityMessage);
        }
      }

      var contentWindow = gPageLoader.getWindow();
      try
      {
        if (typeof(contentWindow.getErrorCode) == 'function' &&
            typeof(contentWindow.getDuffUrl) == 'function' &&
            typeof(contentWindow.getDescription) == 'function')
        {
          var desc = contentWindow.getDescription();
          cdump('Spider: Network Error: ' + gSpider.mCurrentUrl.mUrl + ' ' +
                desc);
          gPageCompleted = true;
        }
        else
        {
          // If you wish to process the DOM of the loaded page,
          // use this.mDocument in this user-defined function.

          // force pagelayout if possible
          try
          {
            if (typeof(this.mDocument.body) != 'undefined' &&
                typeof(this.mDocument.body.offsetHeight) == 'number')
            {
              var dummy = this.mDocument.body.offsetHeight;
            }
          }
          catch(e)
          {
          }

          if (typeof(userOnAfterPage) == 'function')
          {
            try
            {
              userOnAfterPage();
            }
            catch(e)
            {
              var errmsg = 'Error userOnAfterPage User Hook ' + e;
              updateScriptUrlStatus(errmsg);
              cdump('Spider: ' + errmsg);
            }
          }
        }
      }
      catch(ex)
      {
        msg('mOnAfterPage: ' + ex);
      }
      //return true;
      gRestartThread = setTimeout('observeHookSignal()', 1000);
      return false;
    };

  gSpider.mOnStop = function CSpider_mOnStop()
    {
      dlog('CSpider.mOnStop()');

      msg('Stopping... ');

      if (!gInChrome && gCanHaveChromePermissions)
      {
        try
        {
          netscape.security.PrivilegeManager.
            enablePrivilege(gConsoleSecurityPrivileges);
        }
        catch(e)
        {
          msg(e);
          return false;
        }
      }

      gForm.run.disabled = false;
      gForm.save.disabled = false;
      gForm.reset.disabled = false;
      gForm.pause.disabled = true;
      gForm.restart.disabled = true;
      gForm.stop.disabled = true;

      if (typeof(userOnStop) == 'function')
      {
        try
        {
          userOnStop();
        }
        catch(e)
        {
          var errmsg = 'Error: userOnStop User Hook ' + e;
          updateScriptUrlStatus(errmsg);
          cdump('Spider: ' + errmsg);
        }
      }

      msg('Stopped... loaded ' + this.mPagesVisited.length + ' pages');
      cdump('Spider: stopped... loaded ' + this.mPagesVisited.length + ' pages');

      if (gForm.autoquit.checked)
      {
        unregisterConsoleListener();
        unregisterDialogCloser();
        setTimeout('goQuitApplication()', 100);
      }
      return true;
    };

  gSpider.mOnPause = function CSpider_mOnPause()
    {
      dlog('CSpider.mOnPause() ' + gSpider.mState);

      if (!gInChrome && gCanHaveChromePermissions)
      {
        var e;
        try
        {
          netscape.security.PrivilegeManager.
            enablePrivilege(gConsoleSecurityPrivileges);
        }
        catch(e)
        {
          msg(e);
          return false;
        }
      }

      gForm.run.disabled = true;
      gForm.save.disabled = true;
      gForm.reset.disabled = true;
      gForm.pause.disabled = (gPauseState == 'user');
      gForm.restart.disabled = (gPauseState != 'user');
      gForm.stop.disabled = false;

      if (typeof(userOnPause) == 'function')
      {
        try
        {
          userOnPause();
        }
        catch(e)
        {
          var errmsg = 'Error: userOnPause User Hook ' + e;
          updateScriptUrlStatus(errmsg);
          cdump('Spider: ' + errmsg);
        }
      }

      var statemsg;

      if (gPauseState == 'user')
      {
        statemsg = 'Paused ';
        gPauseState = '';
      }
      else
      {
        statemsg = 'Waiting';
      }

      if (gSpider.mState != 'stopped')
      {
        msg(statemsg  + '      : ' +
            (this.mCurrentUrl ? this.mCurrentUrl.mUrl : '')  +
            '\n' +
            'Depth        : ' +
            (this.mCurrentUrl ?  this.mCurrentUrl.mDepth : '') +
            '\n' +
            'Remaining    : ' +
            this.mPagesPending.length +
            '\n' +
            'Total loaded : ' +
            this.mPagesVisited.length);
      }
      return true;
    };

  gSpider.mOnRestart = function mOnRestart()
    {
      dlog('CSpider.mOnRestart()');
      msg('Restarting...');

      if (!gInChrome && gCanHaveChromePermissions)
      {
        try
        {
          netscape.security.PrivilegeManager.
            enablePrivilege(gConsoleSecurityPrivileges);
        }
        catch(e)
        {
          msg(e);
          return false;
        }
      }

      if (gRestartThread)
      {
        clearTimeout(gRestartThread);
        gRestartThread = 0;
      }

      gWaitTime = parseFloat(gForm.waittime.value) * 1000;
      gDebug = gForm.debug.checked;

      gConsoleListener.javascriptErrors   = gForm.javascripterrors.checked;
      gConsoleListener.javascriptWarnings = gForm.javascriptwarnings.checked;
      gConsoleListener.cssErrors          = gForm.csserrors.checked;
      gConsoleListener.httpResponses      = gForm.httpresponses.checked;
      gConsoleListener.chromeErrors       = gForm.chromeerrors.checked;
      gConsoleListener.xblErrors          = gForm.xblerrors.checked;

      gForm.run.disabled = true;
      gForm.save.disabled = true;
      gForm.reset.disabled = true;
      gForm.pause.disabled = false;
      gForm.restart.disabled = true;
      gForm.stop.disabled = false;

      if (typeof(userOnRestart) == 'function')
      {
        try
        {
          userOnRestart();
        }
        catch(e)
        {
          var errmsg = 'Error: userOnRestart User Hook ' + e;
          updateScriptUrlStatus(errmsg);
          cdump('Spider: ' + errmsg);
        }
      }
      return true;
    };

  gSpider.mOnPageTimeout = function CSpider_mOnPageTimeout()
    {
      dlog('CSpider.mOnPageTimeout()');

      var s = 'Timed out loading page: ' + this.mCurrentUrl.mUrl + '.' +
      ' Skipping to next page.\n';

      msg(s);
      cdump('Spider: ' + s);

      if (!gInChrome && gCanHaveChromePermissions)
      {
        try
        {
          netscape.security.PrivilegeManager.
            enablePrivilege(gConsoleSecurityPrivileges);
        }
        catch(e)
        {
          msg(e);
          return false;
        }
      }
      //gForm.run.disabled = true;
      //gForm.save.disabled = true;
      //gForm.reset.disabled = true;
      //gForm.pause.disabled = true;
      //gForm.restart.disabled = false;
      //gForm.stop.disabled = false;

      if (typeof(userOnPageTimeout) == 'function')
      {
        try
        {
          userOnPageTimeout();
        }
        catch(e)
        {
          var errmsg = 'Error: userOnPageTimeout User Hook ' + e;
          updateScriptUrlStatus(errmsg);
          cdump('Spider: ' + errmsg);
        }
      }

      // drop the page that timed out so it isn't tried again
      // XXX I think this ends up skipping the next page...
      // gSpider.mPagesPending.pop();

      // false - keep loading pages.
      return false;
    };

  gSpider.run();
}

function observeHookSignal()
{
  dlog('observeHookSignal() gPageCompleted ' + gPageCompleted + ' ' +
       'gSpider.mState ' + gSpider.mState + ' ' +
       'gForm.hooksignal.checked ' + gForm.hooksignal.checked);

  if (gSpider.mState == 'stopped')
  {
    return;
  }

  if (!gForm.hooksignal.checked)
  {
    dlog('observeHookSignal() gSpider.restart() in  gWaitTime');
    gPageCompleted = true;
    gRestartThread = setTimeout('gSpider.restart()', gWaitTime);
  }
  else if (!gPageCompleted)
  {
    dlog('observeHookSignal() observeHookSignal() in  1000');
    gRestartThread = setTimeout('observeHookSignal()', 1000);
  }
  else
  {
    dlog('observeHookSignal() gSpider.restart() in 100');
    gRestartThread = setTimeout('gSpider.restart()', 100);
  }
}

function userpause()
{
  dlog('userPause()');
  if (gRestartThread)
  {
    clearTimeout(gRestartThread);
    gRestartThread = 0;
  }
  gPauseState = 'user';
  gSpider.pause();
}

function openHelp()
{
  gHelp = window.open('spider-help.htm',
                      'help',
                      'height=600,width=800,resizable=1,scrollbars=1');
}

function unload()
{
  unregisterConsoleListener();
  unregisterDialogCloser();

  if (gHelp && !gHelp.closed)
  {
    gHelp.close();
  }
}

function saveParms()
{
  var path = document.location.href;
  if (path.indexOf('?') != -1)
  {
    path = path.substring(0, path.indexOf('?'));
  }
  // the saved form of the url which encodes the parameters
  // to start Spider must encode the url twice. Once for when
  // it is loaded into Spider, and once after FormPersist has
  // decoded it.
  var saveValue = gForm.url.value;
  gForm.url.value = encodeURIComponent(gForm.url.value);
  path += FormDump(gForm);
  gForm.url.value = saveValue;

  //  var link = '<p><a href="' + path + '">' +  path + '<\/a><\/p>';

  var win = window.open('');
  var doc = win.document;
  var p = doc.createElement('p');
  var a = p.appendChild(doc.createElement('a'));
  a.setAttribute('href', path);
  a.appendChild(doc.createTextNode(path));
  doc.documentElement.appendChild(p);
}

function CPageLoader()
{
  this.loadPending = false;
  this.content = document.getElementById('contentSpider');

  this.handleLoad = function (target) {
    dlog('CPageLoader.handleLoad target.location ' + target.location);

    gPageLoader.loadPending = false;

    if (target.wrappedJSObject) {
      target = target.wrappedJSObject;
    }

    try {
      /*
       * remove onbeforeunload to prevent scam artists from locking us to a page.
       */
      dlog('CPageLoader.handleLoad: target=' + target);
      try {
        dlog('CPageLoader.handleLoad: target.onbeforeunload=' + target.defaultView.onbeforeunload.toSource());
      }
      catch(ex) {
      }
      target.defaultView.onbeforeunload = (function () {});
    }
    catch(ex) {
      dlog('CPageLoader.handleLoad: deleting onbeforeunload: ' + ex);
    }

    gPageLoader.content.removeEventListener('load', gPageLoader.onload, true);
    target.removeEventListener('load', gPageLoader.onload, true);

    gHTTPResponseObserver.unregister();

    gSpider.onLoadPage();
  };

  this.onload = function(evt) {
    dlog('CPageLoader.onload: loadPending ' + gPageLoader.loadPending +
         ', phase ' + evt.eventPhase +
         ', target ' + evt.target +
         ', currentTarget ' + evt.currentTarget +
         ', originalTarget ' + evt.originalTarget +
         ', explicitOriginalTarget ' + evt.explicitOriginalTarget);

    if ( 'location' in evt.target) {
      dlog('CPageLoader.onload: evt.target.location=' + evt.target.location);
    }

    if ( 'location' in evt.originalTarget) {
      dlog('CPageLoader.onload: evt.originalTarget.location=' + evt.originalTarget.location);
    }

    if ( 'location' in evt.explicitOriginalTarget) {
      dlog('CPageLoader.onload: evt.explicitOriginalTarget.location=' + evt.explicitOriginalTarget.location);
    }

    if ( 'location' in evt.currentTarget) {
      dlog('CPageLoader.onload: evt.currentTarget.location=' + evt.currentTarget.location);
    }

    if (!gPageLoader.loadPending) {
      dlog('CPageLoader.onload: load not pending');
      return;
    }

    if ( !('location' in evt.target) || !RegExp('^' + gPageLoader.url.replace(/([\^\$\\\.\*\+\?\(\)\[\]\{\}|])/g, '\\$1') + '[\?#]?').test(evt.target.location)) {
      dlog('CPageLoader.onload: expected load event on ' + gPageLoader.url + ', ignoring load event on evt.target.location=' + evt.target.location);
    }
    else {
      dlog('CPageLoader.onload: found load event on ' + gPageLoader.url + ', on evt.target.location=' + evt.target.location);
      gPageLoader.handleLoad(evt.target);
    }
  };

  this.onDOMContentLoaded = function(evt) {
    dlog('CPageLoader.onDOMContentLoaded: loadPending ' + gPageLoader.loadPending + 
         ', phase ' + evt.eventPhase +
         ', target ' + evt.target +
         ', currentTarget ' + evt.currentTarget +
         ', originalTarget ' + evt.originalTarget +
         ', explicitOriginalTarget ' + evt.explicitOriginalTarget);

    if ( 'location' in evt.target) {
      dlog('CPageLoader.onDOMContentLoaded: evt.target.location=' + evt.target.location);
    }
    if ( 'location' in evt.originalTarget) {
      dlog('CPageLoader.onDOMContentLoaded: evt.originalTarget.location=' + evt.originalTarget.location);
    }
    if ( 'location' in evt.explicitOriginalTarget) {
      dlog('CPageLoader.onDOMContentLoaded: evt.explicitOriginalTarget.location=' + evt.explicitOriginalTarget.location);
    }
    if ( 'location' in evt.currentTarget) {
      dlog('CPageLoader.onDOMContentLoaded: evt.currentTarget.location=' + evt.currentTarget.location);
    }

    if ( !('location' in evt.target) || !RegExp('^' + gPageLoader.url.replace(/([\^\$\\\.\*\+\?\(\)\[\]\{\}|])/g, '\\$1') + '[\?#]?').test(evt.target.location)) {
      dlog('CPageLoader.onDOMContentLoaded: expected load event on ' + gPageLoader.url + ', ignoring load event on evt.target.location=' + evt.target.location);
    }
    else if ('location' in evt.target) {
      dlog('CPageLoader.onDOMContentLoaded: found load event on ' + gPageLoader.url + ', on evt.target.location=' + evt.target.location);
      /*
       * We have the actual content window now and can attach our load handler
       * there in case the redirection processing logic in CPageLoader.onload
       * doesn't catch the load event.
       */
      evt.target.defaultView.addEventListener('load', gPageLoader.onload, true);
      /*
       * wait 60 seconds after onDOMContentLoaded and handle the load regardless if the load event fires
       * on the right document or not.
       * XXX: This may interfere with valgrinding however.
       */
      setTimeout(gPageLoader.handleLoad, 60000, evt.target);

      gPageLoader.content.
        removeEventListener('DOMContentLoaded', gPageLoader.onDOMContentLoaded, true);
    }
  };
}

  CPageLoader.prototype.load =
    function CPageLoader_loadPage(url, referer)
    {
      dlog('CPageLoader_loadPage: url: ' + url + ', referer: ' + referer);

      this.loadPending = true;
      this.url = url;

      if (!referer)
      {
        referer = '';
      }

      var nodeName = this.content.nodeName.toLowerCase();

      this.content.addEventListener('load', this.onload, true);
      this.content.addEventListener('DOMContentLoaded', this.onDOMContentLoaded, true);

      if (nodeName === 'xul:browser')
      {
        dlog('CPageLoader_loadPage: using browser loader');
        // funky interface takes a string for uri, but requires an nsIURI
        // for referer...
        var uri = null;
        try
        {
          uri = Components.classes["@mozilla.org/network/io-service;1"].
            getService(Components.interfaces.nsIIOService).
            newURI(referer, null, null);
        }
        catch(e)
        {
          dlog('CPageLoader_loadPage: failed to create uri, using null : ' + e);
        }

        gHTTPResponseObserver.register();
        this.content.loadURI(url, uri);
      }
      else if (nodeName === 'iframe' || nodeName === 'xul:iframe')
      {
        dlog('CPageLoader_loadPage: using iframe loader');
        gHTTPResponseObserver.register();
        this.content.setAttribute('src', url);
      }
      else
      {
        dlog('CPageLoader_loadPage: invalid content ' + nodeName);
        throw 'CPageLoader_loadPage: invalid content ' + nodeName;
      }
    };

  CPageLoader.prototype.cancel =
    function CPageLoader_cancel()
    {
      dlog('CPageLoader_cancel');
      this.loadPending = false;
      this.content.removeEventListener('load', this.onload, true);
      this.content.removeEventListener('DOMContentLoaded', this.onDOMContentLoaded, true);
      gHTTPResponseObserver.unregister();
    };

  CPageLoader.prototype.getDocument =
    function CPageLoader_getDocument()
    {
      var contentDocument = this.content.contentDocument;
      return contentDocument;
    };

  CPageLoader.prototype.getWindow =
    function CPageLoader_getWindow()
    {
      var contentWindow = this.content.contentWindow;
      return contentWindow;
    };

/*
  From mozilla/toolkit/content
  These files did not have a license
*/

  function canQuitApplication()
  {
    var os = Components.classes["@mozilla.org/observer-service;1"]
      .getService(Components.interfaces.nsIObserverService);
    if (!os)
    {
      dlog('canQuitApplication: unable to get observer service');
      return true;
    }

    try
    {
      var cancelQuit = Components.classes["@mozilla.org/supports-PRBool;1"]
        .createInstance(Components.interfaces.nsISupportsPRBool);
      os.notifyObservers(cancelQuit, "quit-application-requested", null);

      // Something aborted the quit process.
      if (cancelQuit.data)
      {
        dlog('canQuitApplication: something aborted the quit process');
        return false;
      }
    }
    catch (ex)
    {
      dlog('canQuitApplication: ' + ex);
    }
    os.notifyObservers(null, "quit-application-granted", null);
    return true;
  }

  function goQuitApplication()
  {
    dlog('goQuitApplication() called');

    var privs = 'UniversalPreferencesRead UniversalPreferencesWrite ' +
      'UniversalXPConnect';

    try
    {
      netscape.security.PrivilegeManager.enablePrivilege(privs);
    }
    catch(ex)
    {
      throw('goQuitApplication: privilege failure ' + ex);
    }

    if (!canQuitApplication())
    {
      return false;
    }

    unregisterConsoleListener();
    unregisterDialogCloser();

    var kAppStartup = '@mozilla.org/toolkit/app-startup;1';
    var kAppShell   = '@mozilla.org/appshell/appShellService;1';
    var   appService;
    var   forceQuit;

    if (kAppStartup in Components.classes)
    {
      appService = Components.classes[kAppStartup].
        getService(Components.interfaces.nsIAppStartup);
      forceQuit  = Components.interfaces.nsIAppStartup.eForceQuit;

    }
    else if (kAppShell in Components.classes)
    {
      appService = Components.classes[kAppShell].
        getService(Components.interfaces.nsIAppShellService);
      forceQuit = Components.interfaces.nsIAppShellService.eForceQuit;
    }
    else
    {
      throw 'goQuitApplication: no AppStartup/appShell';
    }

    var windowManager = Components.
      classes['@mozilla.org/appshell/window-mediator;1'].getService();

    var windowManagerInterface = windowManager.
      QueryInterface(Components.interfaces.nsIWindowMediator);

    var enumerator = windowManagerInterface.getEnumerator(null);

    while (enumerator.hasMoreElements())
    {
      var domWindow = enumerator.getNext();
      if (("tryToClose" in domWindow) && !domWindow.tryToClose())
      {
        dlog('goQuitApplication: domWindow.tryToClose() is false');
        return false;
      }
      domWindow.close();
    }

    try
    {
      appService.quit(forceQuit);
    }
    catch(ex)
    {
      throw('goQuitApplication: ' + ex);
    }

    return true;
  }

/*
 * Redirections can involve relative paths. To handle these,
 * rely on the subsequent response for the URI to tell us
 * what the effective urls will be.
 */
  var gHTTPResponseRedirectPending = false;

  var gHTTPResponseObserver = {
  observe: function(subject, topic, data)
  {

    var privs = 'UniversalPreferencesRead UniversalPreferencesWrite ' +
    'UniversalXPConnect';

    try
    {
      window.netscape.security.PrivilegeManager.enablePrivilege(privs);
    }
    catch(ex)
    {
      throw('gHTTPResponseObserver: privilege failure ' + ex);
    }

    var response = {};

    try
    {
      window.dlog('gHTTPResponseObserver.observe subject: ' + subject +
                  ', topic: ' + 'data: ' + data);

      var httpChannel = subject.
        QueryInterface(Components.interfaces.nsIHttpChannel);

      if (!httpChannel || !window.gSpider.mCurrentUrl)
      {
        return;
      }

      window.gSpider.mCurrentUrl.mResponses.push(response);

      try
      {
        response.originalURI = httpChannel.originalURI.spec;
      }
      catch(ex)
      {
        window.dlog('gHTTPResponseObserver.observe: httpChannel.originalURI: ' + ex);
      }

      try
      {
        response.URI = httpChannel.URI.spec;
      }
      catch(ex)
      {
        window.dlog('gHTTPResponseObserver.observe: httpChannel.URI: ' + ex);
      }

      try
      {
        response.referrer = httpChannel.referrer.spec;
      }
      catch(ex)
      {
        window.dlog('gHTTPResponseObserver.observe: httpChannel.referrer: ' + ex);
      }

      try
      {
        response.responseStatus = httpChannel.responseStatus;
      }
      catch(ex)
      {
        window.dlog('gHTTPResponseObserver.observe: httpChannel.responseStatus: ' + ex);
      }

      try
      {
        response.responseStatusText = httpChannel.responseStatusText.
          toLowerCase();
      }
      catch(ex)
      {
        window.dlog('gHTTPResponseObserver.observe: httpChannel.responseStatusText: ' + ex);
      }

      try
      {
        response.requestSucceeded = httpChannel.requestSucceeded;
      }
      catch(ex)
      {
        window.dlog('gHTTPResponseObserver.observe: httpChannel.requestSucceeded: ' + ex);
      }

      try
      {
        response.contentType = httpChannel.getResponseHeader('content-type');
      }
      catch(ex)
      {
        window.dlog('gHTTPResponseObserver.observe: getResponseHeader("content-type"): ' + ex);
      }

      try
      {
        response.name = httpChannel.name;
      }
      catch(ex)
      {
        window.dlog('gHTTPResponseObserver.observe: httpChannel.name: ' + ex);
      }

      response.location = '';
      try {
        response.location = httpChannel.getResponseHeader('location');
      }
      catch(ex) {
        window.dlog('gHTTPResponseObserver.observe: httpChannel.getResponseHeader("location"): ' + ex);
      }

      window.dlog('gHTTPResponseObserver.observe response: ' + response.toSource());

      if (gHTTPResponseRedirectPending && RegExp('^' + gPageLoader.url.replace(/([\^\$\\\.\*\+\?\(\)\[\]\{\}|])/g, '\\$1') + '[\/]?$').test(response.originalURI) &&
          (response.requestSucceeded || response.responseStatus == "404")) {
        gHTTPResponseRedirectPending = false;
//      window.gPageLoader.url = response.location.indexOf('http') == 0 ? response.location : response.URI;
        window.gPageLoader.url = response.URI;
        window.dlog('gHTTPResponseObserver.observe complete redirection: ' +
                    'window.gPageLoader.url=' + window.gPageLoader.url);
      }
      else {
        // detect when the url passed to gPageLoader has been redirected
        // and update gPageLoader.url to match.
        if (/301|302|303|307/.test(response.responseStatus) &&
            RegExp('^' + gPageLoader.url.replace(/([\^\$\\\.\*\+\?\(\)\[\]\{\}|])/g, '\\$1') + '[\/]?$').test(response.URI)) {

          gHTTPResponseRedirectPending = true;
          // use the response.originalURI to indicate which response is the
          // result of the redirection.
          window.gPageLoader.url = response.originalURI;
          window.dlog('gHTTPResponseObserver.observe start redirection: ' +
                      'window.gPageLoader.url=' + window.gPageLoader.url);
        }
      }
    }
    catch(e)
    {
      //window.dlog(' ' + e);
    }

  },

  get observerService() {

    var privs = 'UniversalPreferencesRead UniversalPreferencesWrite ' +
    'UniversalXPConnect';

    if (!gInChrome && !gCanHaveChromePermissions)
    {
      return null;
    }

    try
    {
      netscape.security.PrivilegeManager.enablePrivilege(privs);
    }
    catch(ex)
    {
      throw('gHTTPResponseObserver: privilege failure ' + ex);
    }

    try
    {
      return Components.classes["@mozilla.org/observer-service;1"]
      .getService(Components.interfaces.nsIObserverService);
    }
    catch(e)
    {
      dlog(' ' + e);
      return null;
    }
  },

  register: function()
  {
    var privs = 'UniversalPreferencesRead UniversalPreferencesWrite ' +
    'UniversalXPConnect';

    if (!gInChrome && !gCanHaveChromePermissions)
    {
      return;
    }

    try
    {
      netscape.security.PrivilegeManager.enablePrivilege(privs);
    }
    catch(ex)
    {
      throw('gHTTPResponseObserver: privilege failure ' + ex);
    }

    try
    {
      this.observerService.addObserver(this, "http-on-examine-response", false);
      this.observerService.addObserver(this, "http-on-examine-cached-response", false);
    }
    catch(e)
    {
      dlog(' ' + e);
    }
  },

  unregister: function()
  {
    var privs = 'UniversalPreferencesRead UniversalPreferencesWrite ' +
    'UniversalXPConnect';

    if (!gInChrome && !gCanHaveChromePermissions)
    {
      return;
    }

    try
    {
      netscape.security.PrivilegeManager.enablePrivilege(privs);
    }
    catch(ex)
    {
      throw('gHTTPResponseObserver: privilege failure ' + ex);
    }

    try
    {
      this.observerService.removeObserver(this, "http-on-examine-response");
      this.observerService.removeObserver(this, "http-on-examine-cached-response");
      if(gDebug)
      {
        cdump('Spider: Current Url: ' + gSpider.mCurrentUrl.mUrl +
              ', Referer: ' + gSpider.mCurrentUrl.mReferer +
              ', Depth: ' + gSpider.mCurrentUrl.mDepth);
        var responses = gSpider.mCurrentUrl.mResponses;
        for (var iResponse = 0; iResponse < responses.length; iResponse++)
        {
          var response = responses[iResponse];
          cdump('Spider: Response:' +
                ' originalURI: ' + response.originalURI +
                ' URI: ' + response.URI +
                ' referer: ' + response.referrer +
                ' status: ' + response.responseStatus +
                ' status text: ' + response.responseStatusText +
                ' content-type: ' + response.contentType +
                ' succeeded: ' + response.requestSucceeded);

        }
      }
    }
    catch(e)
    {
      dlog(' ' + e);
    }
  }
  };
