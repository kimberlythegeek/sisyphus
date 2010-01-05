/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * bugzilla query to extract urls from bug reports.
 */

function userOnStart()
{
  dlog('userOnStart()');
  gURL = gForm.url.value;

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

  try
  {
    var win = gSpider.mDocument.defaultView;
    if (win.wrappedJSObject)
    {
      win = win.wrappedJSObject;
    }

    //    cdump('XXX win.location.href=' + win.location.href);
    //    cdump('XXX html: ' + win.document.body.innerHTML);
    try
    {
// note this only works if you are logged into bugzilla.
      var url = win.document.getElementById('bug_file_loc').value;
      if (url)
        cdump('url=' + url);
    }
    catch(ex)
    {
      cdump('exception getting url: ' + ex);
//      cdump(win.document.body.innerHTML)
    }

    var attachment;
    var iattachment = 1;

    try
    {
      var bugid = /Bug ([0-9]*).*/.exec(win.document.title)[1];

    }
    catch(ex)
    {
      cdump('exception gettting bugid: ' + ex);
      bugid = '';
    }

    while ( (attachment = win.document.getElementsByName('a' + iattachment)[0]) != null )
    {
      var mime = attachment.nextSibling.nextSibling.innerHTML;
      if (mime.match(/(html|xhtml|xml|xul|svg|image)/))
      {
        attachment = String(attachment);
        attachment = attachment.replace(/bugzilla/, 'bug' + bugid + '.bugzilla');
        cdump('attachment=' + attachment);
//          cdump('mime=' + mime)
      }
      ++iattachment;
    }
  }
  catch(ex)
  {
    cdump('XXX exception: ' + ex);
  }

  completePage();
}

function completePage()
{
  dlog('completePage()');
  collectGarbage();
  gPageCompleted = true;
}


function userOnStop()
{
  dlog('userOnStop()');

}
