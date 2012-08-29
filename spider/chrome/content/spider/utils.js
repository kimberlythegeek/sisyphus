/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */
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
 * The Original Code is Spider Code.
 *
 * The Initial Developer of the Original Code is
 * Bob Clary <http://bclary.com>.
 * Portions created by the Initial Developer are Copyright (C) 2004
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
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

// console listener adapted from
// http://www.mozilla.org/projects/xpcom/using-consoleservice.html

var gConsoleSecurityPrivileges =
  'UniversalXPConnect UniversalBrowserRead UniversalBrowserWrite';

var gConsoleSecurityMessage =
  'Several features such as cross domain access, error logging, \n' +
  'or http logging require security privileges to operate.\n' +
  'Please see Help for more details.';

var gConsoleService;

var gJSDebuggerService;

function msg(s)
{
  if (typeof gOutput == 'undefined' || !gOutput)
  {
    gOutput = document.getElementById('output');
    if (!gOutput && typeof dump == 'function')
    {
      dump(s);
      return;
    }
  }

  while (gOutput.firstChild)
  {
    gOutput.removeChild(gOutput.firstChild);
  }
  var pre = document.createElementNS(xhtmlns, 'pre');
  pre.appendChild(document.createTextNode(s));
  gOutput.appendChild(pre);
}

var gConsoleListener =
{
javascriptErrors: false,
javascriptWarnings: false,
cssErrors: false,
chromeErrors: false,
xblErrors: false,
consoleStrings: null,

observe:function gConsoleListener_Observe( aMessage )
{
  //@JSD_LOG
  // inspired by Basic's consoleDump XPI

  var e;
  var excp1;
  var excp2;
  var msg = '';

  try
  {
    var category;
    var sourcecode;
    var type;
    var typeName = 'typeError';

    var errorMessage =
    aMessage.QueryInterface(Components.interfaces.nsIScriptError);

    if (errorMessage.flags & errorMessage.warningFlag)
    {
      typeName = 'typeWarning';
    }
    else if (errorMessage.flags & errorMessage.exceptionFlag)
    {
      typeName = 'typeException';
    }
    else if (errorMessage.flags & errorMessage.errorFlag)
    {
      typeName = 'typeError';
    }

    if (errorMessage.category == 'content javascript' ||
        errorMessage.category == 'XPConnect JavaScript')
    {
      if (!this.javascriptErrors &&
          (typeName == 'typeError' || typeName == 'typeException'))
      {
        return;
      }
      if (!this.javascriptWarnings && typeName == 'typeWarning')
      {
        return;
      }
    }

    if (errorMessage.category.indexOf('CSS') > -1  && !this.cssErrors)
    {
      return;
    }

    if (errorMessage.category == 'chrome javascript' && !this.chromeErrors)
    {
      return;
    }

    if (errorMessage.category == 'xbl javascript' && !this.xblErrors)
    {
      return;
    }

    if (errorMessage.category == 'content javascript')
    {
      category = 'JavaScript';
    }
    else if (errorMessage.category == 'chrome javascript')
    {
      category = 'Chrome JavaScript';
    }
    else if (errorMessage.category == 'xbl javascript')
    {
      category = 'XBL JavaScript';
    }
    else if (errorMessage.category.indexOf('CSS') > -1)
    {
      category = errorMessage.category;
    }
    else
    {
      category = errorMessage.category;
    }

    msg += category;

    type = this.consoleStrings.getString(typeName);

    msg += ' ' + type + ' ';

    // hack around bug in nsScriptError that forces
    // message to contain JavaScript [Error|Warning]
    msg += errorMessage.message.replace(/JavaScript (Error|Warning): /, '');
    if (msg.substr(msg.length-1) != '.')
    {
      msg += '.';
    }
    msg += ' ';

    if (errorMessage.sourceName)
    {
      msg += this.consoleStrings.
        getFormattedString('errFile',
                           [errorMessage.sourceName]) + ', ';
    }

    if (errorMessage.columnNumber)
    {
      msg += this.consoleStrings.
      getFormattedString('errLineCol',
                         [errorMessage.lineNumber,
                          errorMessage.columnNumber]) +
      ', ';
    }
    else
    {
      msg += this.consoleStrings.
      getFormattedString('errLine',
                         [errorMessage.lineNumber]) +
      ', ';
    }

    if (errorMessage.sourceLine)
    {
      msg += this.consoleStrings.getFormattedString('errCode', ['']) + ' ' +
      errorMessage.sourceLine;
    }
  }
  catch(excp1)
  {
    try
    {
      var consoleMessage =
      aMessage.QueryInterface(Components.interfaces.nsIConsoleMessage);
      msg += consoleMessage.message;
    }
    catch(excp2)
    {
      msg += aMessage;
    }
  }

  msg = msg.replace(/, $/, '.');
  msg = msg.replace(/\n/g, ' ');
  msg += '\n';

  if (typeof(this.onConsoleMessage) == 'function')
  {
    try
    {
      this.onConsoleMessage(msg);
    }
    catch(e)
    {
      var errmsg = 'gConsoleListener_Observe: ' + e + '\n';
      dump(errmsg);
      throw(errmsg);
    }
  }
  else
  {
    dump(msg);
  }
},

QueryInterface: function gConsoleListener_QueryInterface(iid)
{
  if (!iid.equals(Components.interfaces.nsIConsoleListener) &&
      !iid.equals(Components.interfaces.nsISupports))
  {
    throw Components.results.NS_ERROR_NO_INTERFACE;
  }
  return this;
}
};

function registerConsoleListener()
{
  var excp;

  gConsoleListener.javascriptErrors = false;
  gConsoleListener.javascriptWarnings = false;
  gConsoleListener.cssErrors = false;
  gConsoleListener.chromeErrors = false;
  gConsoleListener.xblErrors = false;

  try
  {
    var consoleService = getConsoleService();
    consoleService.registerListener(gConsoleListener);
  }
  catch(excp)
  {
  }

  gConsoleListener.consoleStrings = document.getElementById('console-strings');

  if (!gConsoleListener.consoleStrings)
  {
    // handle the case where we are running in HTML
    // and do not have a string-bundle for the console strings.
    gConsoleListener.consoleStrings = {
    getString: function gConsoleListener_getString(typeName)
    {
      switch (typeName)
      {
      case 'typeError':
      return 'Error';
      case 'typeWarning':
      return 'Warning';
      case 'typeException':
      return 'Exception';
      case 'errCode':
      return 'Source Code:';
      default:
      return 'Unknown';
      }
    },

    getFormattedString:
    function gConsoleListener_getFormattedString(typeName, values)
    {
      var s;
      var v;

      switch(typeName)
      {
      case 'errFile':
        s = 'Source File: %S';
        break;
      case 'errLine':
        s = 'Line: %S';
        break;
      case 'errLineCol':
        s = 'Line: %S, Column: %S';
        break;
      default:
        s = 'Unknown: ';
        for (v in values)
        {
          s += ' %S ';
        }
        break;
      }

      for (v in values)
      {
        s = s.replace(/%S/, v);
      }

      return s;
    }
    };
  }
}

function unregisterConsoleListener()
{
  var excp;

  try
  {
    var consoleService = getConsoleService();
    consoleService.unregisterListener(gConsoleListener);
  }
  catch(excp)
  {
  }
}

function getConsoleService()
{
  if (gConsoleService)
  {
    return gConsoleService;
  }

  var excp;

  try
  {
    gConsoleService =
      Components.classes["@mozilla.org/consoleservice;1"]
      .getService(Components.interfaces.nsIConsoleService);
  }
  catch(excp)
  {
  }

  return gConsoleService;

}

function cdump(s)
{
  var consoleService = getConsoleService();

  var excp;

  try
  {
    consoleService.logStringMessage(s);
  }
  catch(excp)
  {
  }

}

function _noop()
{
}

function _dlog(/* String */ s)
{
  dump('Spider: debug: ' + s.toString() + '\n');
}

function _clog(/* String */ s)
{
  cdump('debug: ' + s.toString() + '\n');
}

var gDebug       = false;
var _dloghash    = {};
_dloghash[true]  = typeof(cdump) == 'function' ? _clog : _dlog;
_dloghash[false] = _noop;

function dlog(/* String */ s)
{
  return _dloghash[gDebug](s);
}

// Thanks to dveditz for the inspiration

function collectGarbage()
{
  try
  {
    var JSD_CTRID = "@mozilla.org/js/jsd/debugger-service;1";
    var jsdIDebuggerService = Components.interfaces.jsdIDebuggerService;
    gJSDebuggerService = Components.classes[JSD_CTRID].
      getService(jsdIDebuggerService);
    gJSDebuggerService.GC();
  }
  catch(ex)
  {
    // cdump('gc: ' + ex);
    // Thanks to igor.bukanov@gmail.com
    var tmp = Math.PI * 1e500, tmp2;
    for (var i = 0; i != 1 << 15; ++i)
    {
      tmp2 = tmp * 1.5;
    }
  }
}

