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
var gPageWait  = 1 * 1000;

function userOnStart()
{
  registerDialogCloser();
}

function userOnStop()
{
  unregisterDialogCloser();
}

function userOnBeforePage()
{
}

function userOnAfterPage()
{
  setTimeout(completePage, gPageWait);
}

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

