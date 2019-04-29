/* -*- Mode: C++; tab-width: 4; indent-tabs-mode: nil; -*- */
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */

function AppInfo()
{
  // See http://developer.mozilla.org/en/docs/Using_nsIXULAppInfo
  var appInfo;

  this.vendor          = 'unknown';
  this.name            = 'unknown';
  this.ID              = 'unknown';
  this.version         = 'unknown';
  this.appBuildID      = 'unknown';
  this.platformVersion = 'unknown';
  this.platformBuildID = 'unknown';

  try
  {
    netscape.security.PrivilegeManager.enablePrivilege('UniversalXPConnect');

    if('@mozilla.org/xre/app-info;1' in Components.classes) 
    {
      // running under Mozilla 1.8 or later
      appInfo = Components
                  .classes['@mozilla.org/xre/app-info;1']
                  .getService(Components.interfaces.nsIXULAppInfo);

      this.vendor          = appInfo.vendor;
      this.name            = appInfo.name;
      this.ID              = appInfo.ID;
      this.version         = appInfo.version;
      this.appBuildID      = appInfo.appBuildID;
      this.platformVersion = appInfo.platformVersion;
      this.platformBuildID = appInfo.platformBuildID;
    }
  }
  catch(e)
  {
  }

  if (this.vendor == 'unknown')
  {
    var ua = navigator.userAgent;
    var cap = ua.match(/rv:([\d.ab+]+).*Gecko\/(\d{8,8}) ([\S]+)\/([\d.]+)/);

    if (cap && cap.length == 5)
    {
      this.vendor          = navigator.vendor ? navigator.vendor : 'Mozilla';
      this.name            = cap[3];
      this.version         = cap[4];
      this.appBuildID      = cap[2] + '00';
      this.platformVersion = cap[1];
      this.platformBuildID =  this.appBuildID;
    }
  }
}
