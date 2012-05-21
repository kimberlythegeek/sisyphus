/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at http://mozilla.org/MPL/2.0/. */

/*
 * Spider hook function to check if spider is working.
 */


function userOnStart()
{
}

function userOnBeforePage()
{
}

function userOnAfterPage()
{
  var win = gSpider.mDocument.defaultView;
  if (win.wrappedJSObject)
  {
    win = win.wrappedJSObject;
  }

  dumpObject('navigator', win.navigator);

  for (var i = 0; i < win.navigator.mimeTypes.length; i++)
  {
    dumpObject('navigator.mimeTypes[' + i + ']', win.navigator.mimeTypes[i]);
  }

  for (var i = 0; i < win.navigator.plugins.length; i++)
  {
    dumpObject('navigator.plugins[' + i + ']', win.navigator.plugins[i]);
  }

  gPageCompleted = true;
}

function dumpObject(name, object)
{
  for (var p in object)
  {
    if (/(string|number)/.test(typeof object[p]))
    {
      cdump(name + '.' + p + ':' + object[p]);
    }
  }

}

function userOnStop()
{
}


gConsoleListener.onConsoleMessage = 
function userOnConsoleMessage(s)
{
  dump(s);
};
