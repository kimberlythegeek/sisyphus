/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * top-sites user hook function: disable dialogs and complete on page load.
 */

var gPageCount = 0;
var gPageLimit = 1;

function userOnBeforePage()
{
  registerDialogCloser();
}

function userOnAfterPage()
{
  completePage();
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
  unregisterDialogCloser();
}

