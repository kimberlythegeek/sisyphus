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
   
/*
  Check robots.txt to see if this ua is blocked from spidering url
  return true if blocked, false if not

  url = absolute url
  ua  = short spider name

  http://www.robotstxt.org/wc/robots.html
*/
function isRobotBlocked(url, ua)
{
  // remove query string
  url = url.replace(/\?.*/,'');

  var list = url.split('//');
  // list = [protcol, domain + path]

  var protocol = list[0];

  if (!protocol.match(/^http[s]?:/))
  {
    return false;
  }

  list = list[1].split(/\//);
  // list = [domain, path1, path2, ...]

  var domain = list[0];

  var path = '';
  for (var i = 1; i < list.length; i++)
  {
    path += '/' + list[i];
  }

  if (!(domain in isRobotBlocked.domainHash))
  {
    loadRobotsTxt(ua, protocol, domain)
      }

  list = isRobotBlocked.domainHash[domain];

  for (i = 0; i < list.length; i++)
  {
    if (path.indexOf(list[i]) == 0)
    {
      return true;
    }
  }

  return false;
}

isRobotBlocked.domainHash = {};
isRobotBlocked.inChrome  = (document.location.href.indexOf('chrome://') == 0);

function loadRobotsTxt(ua, protocol, domain)
{
  var excp;
  if (!gInChrome && gCanHaveChromePermissions)
  {
    try
    {
      netscape.security.PrivilegeManager.
        enablePrivilege('UniversalBrowserRead');
    }
    catch(excp)
    {
      msg(excp);
    }
  }

  try
  {
    var robotstxt = protocol + '//' + domain + '/robots.txt';
    var xmlHttpRequest = new XMLHttpRequest();
    xmlHttpRequest.open('GET', robotstxt, false);
    xmlHttpRequest.send(null);
    if (xmlHttpRequest.statusText != 'OK')
    {
      isRobotBlocked.domainHash[domain] = []; 
      return;
    }

  }
  catch (excp)
  {
    dlog('loadRobotsTxt Exception: ua=' + ua + ', protocol=' + protocol + ', domain=' + domain + ' ' +  excp);
    isRobotBlocked.domainHash[domain] = []; 
    return;
  }

  ua = ua.toLowerCase();

  var lines = xmlHttpRequest.responseText.split(/[\r\n]/);
  var list  = [];
  var uamatch = false;
  var state = 'outside';

  for (var i = 0; i < lines.length; i++)
  {
    var line = lines[i];

    if (line.match(/^[\s]*#/))
    {
      // ignore comment lines
      continue;
    }

    if (line.match(/^[\s]*$/))
    {
      // completely blank line is a record boundary
      uamatch = false;
      state = 'outside';
      continue;
    }

    var colonPos = line.indexOf(':');
    if (colonPos == -1)
    {
      continue;
    }

    var rule  = line.substr(0, colonPos).toLowerCase();

    if (rule != 'user-agent' && rule != 'disallow')
    {
      // ignore unknown rules
      continue;
    }

    // strip trailing comments
    // line = line.replace(/#.*/, '');

    var value = line.substr(colonPos + 1).replace(/^[\s\t]+/, '');
    value = value.replace(/[\s\t]+^/, '');

    var uaregx;

    switch(state)
    {
    case 'outside': // not in a record
      if (rule == 'user-agent')
      {
        if (value == '*')
        {
          // clear disallowed list, match any ua
          list = [];
          uamatch = true;
        }
        else
        {
          uaregx = new RegExp(ua, 'i');
          uamatch = uaregx.test(value);
        }
        state = 'ua';
      }
      else
      {
        // missing user-agent:
        // assume user-agent: *
        // clear disallowed list, match any ua
        list = [];
        uamatch = true; 
        // ignore remaining user-agents in this record
        state = 'disallow';
        if (value)
        {
          list.push(value);
        }
      }
      break;

    case 'ua':  // in record, only user-agent: so far
      if (rule == 'user-agent')
      {
        if (value == '*')
        {
          // clear disallowed list, match any ua
          list = [];
          uamatch = true;
        }
        else
        {
          uaregx = new RegExp(ua, 'i');
          uamatch = uamatch || uaregx.test(value);
        }
      }
      else if (uamatch)
      {
        if (value)
        {
          list.push(value);
        }
        else
        {
          // empty disallow: clears disallowed list
          list = [];
        }

      }
      break;

    case 'disallow':
      if (rule == 'disallow' && uamatch)
      {
        if (value)
        {
          list.push(value);
        }
        else
        {
          // empty disallow: clears disallowed list
          list = [];
        }
      }
      break;

    default:
      break;
    }
  }
  isRobotBlocked.domainHash[domain] = list; 
}


