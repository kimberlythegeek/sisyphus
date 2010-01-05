/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */


var Ci = Components.interfaces;
var Cc = Components.classes;
var Cr = Components.results;

var rdfsvc;
var bmds;
var bmsvc;
var bmremoteds;
var bmstoolbar;
var bmsroot;

var navbms;
var navroot;
var iosvc;

var w;

function uri(spec) {
  return iosvc.newURI(spec, null, null);
}

var gBookmarkCount = 0;
var gBookmarkLimit = 10;
var gPageCount = 0;
var gPageLimit = 90;

function userOnStart()
{
  dlog('userOnStart()');

  try
  {
    cdump('trying to set up bookmarks service for trunk');
    navbms = Cc["@mozilla.org/browser/nav-bookmarks-service;1"].getService(Ci.nsINavBookmarksService);
    navroot = navbms.bookmarksMenuFolder;
    iosvc = Cc["@mozilla.org/network/io-service;1"].getService(Ci.nsIIOService);
  }
  catch(ex)
  {
    cdump('trying to set up bookmarks service for 1.8');
    try
    {
      w = window.open('about:blank'); // open window to get chrome toolbars?
/*
  var bmsvc = Cc["@mozilla.org/browser/bookmarks-service;1"].getService(Ci.nsIBookmarksService);
*/
      rdfsvc = Cc['@mozilla.org/rdf/rdf-service;1'].getService(Ci.nsIRDFService);
      bmds = rdfsvc.GetDataSource('rdf:bookmarks');
      bmsvc = bmds.QueryInterface(Ci.nsIBookmarksService);
      bmremoteds = bmds.QueryInterface(Ci.nsIRDFRemoteDataSource);
      bmstoolbar = bmsvc.getBookmarksToolbarFolder();
      bmsroot = bmsvc.getParent(bmstoolbar);
    }
    catch(ex2)
    {
      cdump('Caught ' + ex2);
    }

  }
}


function userOnBeforePage()
{
  dlog('userOnBeforePage()');
  registerDialogCloser();
}

function userOnPause()
{
  dlog('userOnPause()');
}

function userOnAfterPage()
{
  dlog('userOnAfterPage()');
  unregisterDialogCloser();

  if (gPageCount++ >= gPageLimit)
  {
    setTimeout("gSpider.stop()", 0);
    return;
  }

  if (gBookmarkCount++ < gBookmarkLimit)
  {
    try
    {
      if (bmsvc)
      {
        bmsvc.createBookmarkInContainer(gSpider.mDocument.title, gSpider.mCurrentUrl.mUrl, '', '', null, null, bmsroot, -1);
        bmremoteds.Flush();
//      bmsvc.addBookmarkImmediately(gSpider.mCurrentUrl.mUrl, gSpider.mDocument.title, 0, null)
      }
      else if (navbms)
      {
/*
        dlog('navroot: ' + navroot);
        dlog('url: ' + gSpider.mCurrentUrl.mUrl);
        dlog('uri(url): ' + uri(gSpider.mCurrentUrl.mUrl));
        dlog('navbms: ' + navbms);
        dlog('navbms.DEFAULT_INDEX: ' + navbms.DEFAULT_INDEX);
        dlog('title: ' + gSpider.mDocument.title);
*/
        navbms.insertBookmark(navroot, uri(gSpider.mCurrentUrl.mUrl), navbms.DEFAULT_INDEX, gSpider.mDocument.title);
      }
    }
    catch(ex)
    {
      cdump(ex);
    }
  }

  gPageCompleted = true;
}

function userOnStop()
{
  dlog('userOnStop()');
  if (typeof w != 'undefined')
  {
    w.close();
  }
}

