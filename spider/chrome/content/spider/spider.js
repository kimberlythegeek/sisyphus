/* -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */
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

// https://developer.mozilla.org/en-US/docs/Mozilla/Tech/XPCOM/Reference/Interface/nsIWebProgressListener
// https://developer.mozilla.org/en-US/docs/Mozilla/JavaScript_code_modules/XPCOMUtils.jsm

var Cc = Components.classes;
var Ci = Components.interfaces;
var Cu = Components.utils;

Cu.import('resource://gre/modules/XPCOMUtils.jsm');

function loadHandler(evt)
{
  this.removeEventListener('load', loadHandler, false);
  try
  {
    window.dlog('loadHandler: timeStamp=' + evt.timeStamp +
         ', bubbles=' + evt.bubbles +
         ', currentTarget=' + evt.currentTarget +
         ', eventPhase=' + evt.eventPhase +
         ', target=' + evt.target +
         ', originalTarget=' + evt.originalTarget +
         ', type=' + evt.type);
  }
  catch(ex)
  {
    window.dlog('loadHandler: exception: ' + ex + ', ' + ex.stack);
  }
  //https://developer.mozilla.org/en-US/docs/Mozilla/Tech/XUL/browser#m-addProgressListener
  contentSpider = document.getElementById('contentSpider');
  contentSpider.addProgressListener(gProgressListener);

}

this.addEventListener('load', loadHandler, false);

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

function init(evt)
{
  window.dlog('init: timeStamp=' + evt.timeStamp +
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
    catch(ex)
    {
    }
  }

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
    gForm.fileurls.checked   = (oArguments.fileurls == true);
    gForm.debug.checked      = (oArguments.debug == true);
    gForm.javascripterrors.checked  = (oArguments.jserrors == true);
    gForm.javascriptwarnings.checked  = (oArguments.jswarnings == true);
    gForm.chromeerrors.checked  = (oArguments.chromeerrors == true);
    gForm.xblerrors.checked  = (oArguments.xblerrors == true);
    gForm.csserrors.checked  = (oArguments.csserrors == true);
    gForm.httprequests.checked = (oArguments.httprequests == true);
    gForm.invisible          = (oArguments.invisible == true);
    gForm.scripturl.value = oArguments.hook;
  }

  gDebug = gForm.debug.checked;

  if (gForm.invisible)
    document.getElementById('contentSpider').style.visibility = 'hidden';

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

  var url = gForm.url.value;
  var domain = gForm.domain.value;
  var depth = parseInt(gForm.depth.value);
  var restrict = gForm.restrict.checked;
  var timeout = parseFloat(gForm.timeout.value);
  var respectrobotrules = gForm.respectrobotrules.checked;
  var fileurls = gForm.fileurls.checked;
  gWaitTime = parseFloat(gForm.waittime.value) * 1000;
  gDebug = gForm.debug.checked;

  gConsoleListener.javascriptErrors   = gForm.javascripterrors.checked;
  gConsoleListener.javascriptWarnings = gForm.javascriptwarnings.checked;
  gConsoleListener.cssErrors          = gForm.csserrors.checked;
  gConsoleListener.httprequests       = gForm.httprequests.checked;
  gConsoleListener.chromeErrors       = gForm.chromeerrors.checked;
  gConsoleListener.xblErrors          = gForm.xblerrors.checked;

  if (gForm.scripturl.value)
  {
    var scripturl = gForm.scripturl.value.replace(/[ \t]/g, '');
    var excp;
    var excpmsg;
    loadScript(scripturl);
    if (loadScript.compile_success)
      updateScriptUrlStatus('Compile Successful');
    else {
      updateScriptUrlStatus('Compile Failed');
      var contentWindow = document.getElementById('contentSpider').contentWindow.wrappedJSObject;
      contentWindow.document.body.innerHTML = loadScript.compile_message;
      throw(loadScript.compile_message);
    }
  }

  gPageLoader = new CPageLoader(
    document.getElementById('contentSpider'),
    (function () { gSpider.onLoadPage(); }),
    (function () { gSpider.onLoadPageTimeout(); }),
    timeout
  );

  gSpider = new CSpider(url, domain, restrict, depth, gPageLoader, timeout,
                        true, respectrobotrules, fileurls);

  // CSpider is a strategy pattern. You customize its
  // behavior by specifying the following functions which
  // will be called by CSpider on your behalf.

  gSpider.mOnStart = function CSpider_mOnStart()
  {
    window.dlog('CSpider.mOnStart ' + this.mState);
    update_status('Starting...');

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
          (gForm.fileurls.checked           ? '-fileurls '                                : '') +
          (gForm.debug.checked              ? '-debug '                                   : '') +
          (gForm.javascripterrors.checked   ? '-jserrors '                                : '') +
          (gForm.javascriptwarnings.checked ? '-jswarnings '                              : '') +
          (gForm.chromeerrors.checked       ? '-chromeerrors '                            : '') +
          (gForm.xblerrors.checked          ? '-xblerrors '                               : '') +
          (gForm.csserrors.checked          ? '-csserrors '                               : '') +
          (gForm.httprequests.checked       ? '-httprequests '                           : '') +
          (gForm.invisible                  ? '-invisible '                               : '')
         );

    gForm.run.disabled = true;
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
      catch(ex)
      {
        var errmsg = 'Error: userOnStart User Hook ' + ex + ', ' + ex.stack;
        updateScriptUrlStatus(errmsg);
        cdump('Spider: ' + errmsg);
      }
    }

    return true;
  };

  gSpider.mOnBeforePage = function CSpider_mOnBeforePage()
  {
    window.dlog('CSpider.mOnBeforePage ' + this.mState);

    gPageCompleted = false;

    update_status('Loading');

    cdump('Spider: Begin loading ' + this.mCurrentUrl.mUrl);

    if (typeof(userOnBeforePage) == 'function')
    {
      try
      {
        userOnBeforePage();
      }
      catch(ex)
      {
        var errmsg = 'Error: userOnBeforePage User Hook ' + ex + ', ' + ex.stack;
        updateScriptUrlStatus(errmsg);
        cdump('Spider: ' + errmsg);
      }
    }

    return true;
  };

  gSpider.mOnAfterPage = function CSpider_mOnAfterPage()
  {
    window.dlog('CSpider.mOnAfterPage ' + this.mState);

    update_status('Page loaded');

    cdump('Spider: Finish loading ' + this.mCurrentUrl.mUrl);

    cdump('Spider: Current Url: ' + this.mCurrentUrl.mUrl +
          ', Referer: ' + this.mCurrentUrl.mReferer +
          ', Depth: ' + this.mCurrentUrl.mDepth);
    if (gConsoleListener.httprequests)
    {
      for (var request_uri in gPageLoader.requests)
      {
        cdump('Spider: HTTP Request:' + request_uri);
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
        catch(ex)
        {
        }

        if (typeof(userOnAfterPage) == 'function')
        {
          try
          {
            userOnAfterPage();
          }
          catch(ex)
          {
            var errmsg = 'Error userOnAfterPage User Hook exception: ' + ex + ', ' + ex.stack;
            updateScriptUrlStatus(errmsg);
            cdump('Spider: ' + errmsg);
          }
        }
      }
    }
    catch(ex)
    {
      update_status('Page loaded', 'mOnAfterPage: exception: ' + ex + ', ' + ex.stack);
    }
    gRestartThread = setTimeout('observeHookSignal()', 1000);
    return false;
  };

  gSpider.mOnStop = function CSpider_mOnStop()
  {
    window.dlog('CSpider.mOnStop ' + this.mState);

    update_status('Stopping...');

    gForm.run.disabled = false;
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
      catch(ex)
      {
        var errmsg = 'Error: userOnStop User Hook exception: ' + ex + ', ' + ex.stack;
        updateScriptUrlStatus(errmsg);
        cdump('Spider: ' + errmsg);
      }
    }

    update_status('Stopped');
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
    window.dlog('CSpider.mOnPause ' + gSpider.mState);

    gForm.run.disabled = true;
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
      catch(ex)
      {
        var errmsg = 'Error: userOnPause User Hook exception: ' + ex + ', ' + ex.stack;
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

    if (gSpider.mState != 'stopped') {
      update_status(statemsg);
    }
    return true;
  };

  gSpider.mOnRestart = function mOnRestart()
  {
    window.dlog('CSpider.mOnRestart ' + this.mState);
    update_status('Restarting...');

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
    gConsoleListener.httprequests       = gForm.httprequests.checked;
    gConsoleListener.chromeErrors       = gForm.chromeerrors.checked;
    gConsoleListener.xblErrors          = gForm.xblerrors.checked;

    gForm.run.disabled = true;
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
      catch(ex)
      {
        var errmsg = 'Error: userOnRestart User Hook exception: ' + ex + ', ' + ex.stack;
        updateScriptUrlStatus(errmsg);
        cdump('Spider: ' + errmsg);
      }
    }
    return true;
  };

  gSpider.mOnPageTimeout = function CSpider_mOnPageTimeout()
  {
    window.dlog('CSpider.mOnPageTimeout ' + this.mState);

    update_status('Timed out loading page', 'Skipping to next page');
    cdump('Spider: Timed out loading page: ' + this.mCurrentUrl.mUrl + '.' +
      ' Skipping to next page.\n');

    if (typeof(userOnPageTimeout) == 'function')
    {
      try
      {
        userOnPageTimeout();
      }
      catch(ex)
      {
        var errmsg = 'Error: userOnPageTimeout User Hook exception: ' + ex + ', ' + ex.stack;
        updateScriptUrlStatus(errmsg);
        cdump('Spider: ' + errmsg);
      }
    }

    // false - keep loading pages.
    return false;
  };

  gSpider.run();
}

function observeHookSignal()
{
  window.dlog('observeHookSignal() gPageCompleted ' + gPageCompleted + ' ' +
       'gSpider.mState ' + gSpider.mState + ' ' +
       'gForm.hooksignal.checked ' + gForm.hooksignal.checked);

  if (gSpider.mState == 'stopped')
  {
    return;
  }

  if (!gForm.hooksignal.checked)
  {
    window.dlog('observeHookSignal() gSpider.restart() in  gWaitTime');
    gPageCompleted = true;
    gRestartThread = setTimeout('gSpider.restart()', gWaitTime);
  }
  else if (!gPageCompleted)
  {
    window.dlog('observeHookSignal() observeHookSignal() in  1000');
    gRestartThread = setTimeout('observeHookSignal()', 1000);
  }
  else
  {
    window.dlog('observeHookSignal() gSpider.restart() in 100');
    gRestartThread = setTimeout('gSpider.restart()', 100);
  }
}

function userpause()
{
  window.dlog('userPause()');
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

function onVisibility(source)
{
  var browser = document.getElementById('contentSpider');
  var visibility = browser.style.visibility;
  browser.style.visibility = (visibility == 'hidden') ? '' : 'hidden';
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

function update_status(state, status) {
  function pad(prefix, length) {
    for (var i = 0; i < length; i++)
      prefix += ' ';
    return prefix.substring(0, length) + ': '
  }
  var padding = 10;
  var s = '';
  var depth = 0;
  status = status || 'Done';
  if (gSpider.mCurrentUrl) {
    s = pad(state, padding) + gSpider.mCurrentUrl.mUrl + '\n';
    depth = gSpider.mCurrentUrl.mDepth;
  }
  else {
    s = pad('Idle', padding)
  }
  if (status) {
    s += pad('Status', padding) + status + '\n';
  }
  s += pad('Counts', padding) + 'Depth ' + depth + ', ' +
    ' Pending ' + gSpider.mPagesPending.length + ', ' +
    'Visited ' + gSpider.mPagesVisited.length;
  msg(s);
}

var gProgressListener = {
  QueryInterface: XPCOMUtils.generateQI([Ci.nsIWebProgressListener,
                                         Ci.nsISupportsWeakReference]),

  request_to_str: function(aRequest) {
    var s = 'Request: ';

    if (!aRequest)
      s += aRequest;
    else {
      s += aRequest.name;
      try { s+= ' 0x' + aRequest.status.toString(16); } catch(ex) {}
    }
    return s;
  },

  onProgressChange: function (aWebProgress, aRequest,
                              aCurSelfProgress, aMaxSelfProgress,
                              aCurTotalProgress, aMaxTotalProgress) {},

  onStateChange: function (aWebProgress, aRequest, aStateFlags, aStatus) {
    /*
      aStateFlags Flags indicating the new state. This value is a
      combination of one of the State Transition Flags and one or more
      of the State Type Flags defined above. Any undefined bits are
      reserved for future use.
    */
    if (gDebug) {
      var state_message = 'State: ';
      var state_name;
      for (state_name in Ci.nsIWebProgressListener) {
        if (state_name.indexOf('STATE_') == 0) {
          if (aStateFlags & Ci.nsIWebProgressListener[state_name])
            state_message += state_name + ' ';
        }
      }
      state_message = state_message.trimRight();
      dlog('onStateChange: ' + this.request_to_str(aRequest) + ' ' + state_message + ' 0x' + aStatus.toString(16));
    }
    if ((aStateFlags & Ci.nsIWebProgressListener.STATE_STOP) &&
        (aStateFlags & Ci.nsIWebProgressListener.STATE_IS_WINDOW) &&
        aStatus == 0) {
      dlog('onStateChange: handleLoad');
      gPageLoader.handleLoad();
    }
  },

  onLocationChange: function (aWebProgress, aRequest, aLocationURI, aFlags) {
    /*
      aLocation The URI of the location that is being loaded.

      aFlags This is a value which explains the situation or the
      reason why the location has changed. Optional from Gecko 11

      If the location is changed to an error page, we must stop the
      load instead of waiting for a timeout.

    */
    if (gDebug) {
      var state_message = '';
      var state_name;
      for (state_name in Ci.nsIWebProgressListener) {
        if (state_name.indexOf('LOCATION_') == 0) {
          if (aFlags & Ci.nsIWebProgressListener[state_name])
            state_message += state_name + ' ';
        }
      }
      state_message = state_message.trimRight();
      dlog('onLocationChange: ' + this.request_to_str(aRequest) + ' ' + aLocationURI.spec + ' ' + state_message);
    }

    if (aFlags && (aFlags & Ci.nsIWebProgressListener.LOCATION_CHANGE_ERROR_PAGE)) {
      dlog('onLocationChange: force timeout due to ERROR_PAGE current uri ' +
           (gSpider.mCurrentUrl ? gSpider.mCurrentUrl.mUrl : 'null'));
      gPageLoader.ontimeout();
    }
    else {
      dlog('onLocationChange: original ' +
           (gSpider.mCurrentUrl ? gSpider.mCurrentUrl.mUrl : 'null') +
           ' final ' + aLocationURI.spec);
    }
  },

  onStatusChange: function (aWebProgress, aRequest, aStatus, aMessage) {
    if (aRequest) {
      dlog('onStatusChange: ' + this.request_to_str(aRequest) + ' ' + aStatus + ' ' + aMessage);
      if (aRequest.name)
        gPageLoader.requests[aRequest.name] = 1;
    }
    if (aMessage) {
      update_status('Loading', aMessage);
    }
  },

  onSecurityChange: function (aWebProgress, aRequest, aState) {},
}

function CPageLoader(content_element, onload_callback, ontimeout_callback, timeout_interval)
{
  window.dlog('CPageLoader()');

  this.requests = {};
  this.onload_callback = onload_callback;
  this.ontimeout_callback = ontimeout_callback;
  this.ontimeout = (function () {
    window.dlog('CPageLoader.ontimeout()');
    this.ontimeout_ccallwrapper = null;
    this.cancel();
    this.ontimeout_callback();
  });
  this.timeout_interval = (timeout_interval || 60) * 1000;
  this.ontimeout_ccallwrapper = null;
  this.loadPending = false;
  this.content = content_element;
  this.timer_handleLoad = null;
}

CPageLoader.prototype.handleLoad = function () {

  try {
    clearTimeout(gPageLoader.timer_handleLoad);
    if (gPageLoader.ontimeout_ccallwrapper) {
      gPageLoader.ontimeout_ccallwrapper.cancel();
      gPageLoader.ontimeout_ccallwrapper = null;
    }

    gPageLoader.loadPending = false;
  }
  catch(ex) {
    window.dlog('CPageLoader.handleLoad: exception: ' + ex + ', ' + ex.stack);
    return;
  }

  gPageLoader.onload_callback();
};

CPageLoader.prototype.load = function CPageLoader_loadPage(url, referer) {
  window.dlog('CPageLoader.loadPage: ' +
       'url: ' + url + ', referer: ' + referer);

  this.requests = {};
  this.loadPending = true;
  this.url = url;

  if (!referer)
  {
    referer = '';
  }

  var nodeName = this.content.nodeName.toLowerCase();

  if (nodeName === 'xul:browser')
  {
    window.dlog('CPageLoader_loadPage: using browser loader');
    // funky interface takes a string for uri, but requires an nsIURI
    // for referer...
    var uri = null;
    try
    {
      uri = Components.classes['@mozilla.org/network/io-service;1'].
        getService(Components.interfaces.nsIIOService).
        newURI(referer, null, null);
    }
    catch(ex)
    {
      window.dlog('CPageLoader_loadPage: failed to create uri, using null exception: : ' + ex + ', ' + ex.stack);
    }

    this.content.stop();
    this.content.loadURI('about:blank', null);
    this.ontimeout_ccallwrapper = new CCallWrapper(this, this.timeout_interval, 'ontimeout');
    CCallWrapper.asyncExecute(this.ontimeout_ccallwrapper);
    this.content.loadURI(url, uri);
  }
  else if (nodeName === 'iframe' || nodeName === 'xul:iframe')
  {
    window.dlog('CPageLoader_loadPage: using iframe loader');
    this.content.stop();
    this.content.setAttribute('src', 'about:blank');
    this.ontimeout_ccallwrapper = new CCallWrapper(this, this.timeout_interval, 'ontimeout');
    CCallWrapper.asyncExecute(this.ontimeout_ccallwrapper);
    this.content.setAttribute('src', url);
  }
  else
  {
    window.dlog('CPageLoader_loadPage: invalid content ' + nodeName);
    throw 'CPageLoader_loadPage: invalid content ' + nodeName;
  }
};

CPageLoader.prototype.cancel =
  function CPageLoader_cancel()
{
  window.dlog('CPageLoader.cancel()');
  this.loadPending = false;
  this.content.stop();
};

CPageLoader.prototype.getDocument =
  function CPageLoader_getDocument()
{
  window.dlog('CPageLoader.getDocument()');
  var contentDocument = this.content.contentDocument;
  return contentDocument;
};

CPageLoader.prototype.getWindow =
  function CPageLoader_getWindow()
{
  window.dlog('CPageLoader.getWindow()');
  var contentWindow = this.content.contentWindow;
  return contentWindow;
};

/*
  From mozilla/toolkit/content
  These files did not have a license
*/

function canQuitApplication()
{
  var os = Components.classes['@mozilla.org/observer-service;1']
    .getService(Components.interfaces.nsIObserverService);
  if (!os)
  {
    window.dlog('canQuitApplication: unable to get observer service');
    return true;
  }

  try
  {
    var cancelQuit = Components.classes['@mozilla.org/supports-PRBool;1']
      .createInstance(Components.interfaces.nsISupportsPRBool);
    os.notifyObservers(cancelQuit, 'quit-application-requested', null);

    // Something aborted the quit process.
    if (cancelQuit.data)
    {
      window.dlog('canQuitApplication: something aborted the quit process');
      return false;
    }
  }
  catch (ex)
  {
    window.dlog('canQuitApplication: ' + ex);
  }
  os.notifyObservers(null, 'quit-application-granted', null);
  return true;
}

function goQuitApplication()
{
  window.dlog('goQuitApplication() called');

  var privs = 'UniversalPreferencesRead UniversalPreferencesWrite ' +
    'UniversalXPConnect';

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
    if (('tryToClose' in domWindow) && !domWindow.tryToClose())
    {
      window.dlog('goQuitApplication: domWindow.tryToClose() is false');
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

