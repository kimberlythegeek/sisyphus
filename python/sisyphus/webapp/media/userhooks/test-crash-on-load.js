/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * top-sites user hook function:
 *
 * - disable dialogs on start,
 * - wait for the specified period after each page loads,
 * - load the specified number of linked pages before stopping,
 * - enable dialogs on stop.
 */

var gPageCount = 0;
var gPageLimit = 1;
var gPageWait  = 5 * 1000;

function userOnStart()
{
  dlog('userOnStart()');
  registerDialogCloser();

  var rv      = 'unknown';
  var rvmatch = navigator.userAgent.match(/rv:([\w.]*)/);
  if (rvmatch && rvmatch.length >= 2)
    rv = rvmatch[1];

  cdump('rv:' + rv + ' ' + navigator.buildID)
}

function userOnStop()
{
  dlog('userOnStop()');
  unregisterDialogCloser();
}

function userOnBeforePage()
{
  dlog('userOnBeforePage()');
  window.moveTo(0, 0);
  window.resizeTo(screen.availWidth, screen.availHeight);
}

function userOnAfterPage()
{
  dlog('userOnAfterPage()');
  setTimeout(completePage, gPageWait);
}

userOnPageTimeout = userOnAfterPage;

function completePage()
{
  dlog('completePage()');

  ++gPageCount;

  if (gPageCount >= gPageLimit)
  {
    gSpider.stop();
  }

  gPageCompleted = true;
}

