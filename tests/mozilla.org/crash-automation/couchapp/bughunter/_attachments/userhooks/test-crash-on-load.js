/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * top-sites user hook function: disable dialogs and complete on page load.
 */

function userOnBeforePage()
{
  registerDialogCloser();
}

function userOnAfterPage()
{
  gSpider.stop();
  gPageCompleted = true;
  unregisterDialogCloser();
}
