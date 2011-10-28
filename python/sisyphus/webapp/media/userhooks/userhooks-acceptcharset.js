/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * top-sites user hook function 
 */

var gPageCompleted = false;

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
    var doc = win.document;

    var xhr1 = new XMLHttpRequest();
    var xhr1_responseheaders;
    var xhr1_responsetext;

    xhr1.open('GET', doc.location.href, false); // sync request
    xhr1.send(null);
    xhr1_responseheaders = xhr1.getAllResponseHeaders();
    xhr1_responsetext    = xhr1.responseText;

    var xhr2 = new XMLHttpRequest();
    var xhr2_responseheaders;
    var xhr2_responsetext;
    xhr2.open('GET', doc.location.href, false); // sync request
    xhr2.setRequestHeader('Accept-Charset', 'ISO-8859-1,utf-8;q=0.7,*;q=0.7');
    xhr2.send(null);
    xhr2_responseheaders = xhr2.getAllResponseHeaders();
    xhr2_responsetext    = xhr2.responseText;

    // http://www.ietf.org/rfc/rfc2616.txt
    var r = /charset=([^ ()<>@,;:\\\"\/\[\]\?=\{\}\t\r\n]+)/;
    var captures1 = r.exec(xhr1_responseheaders);
    var captures2 = r.exec(xhr2_responseheaders);
    var charset1 = captures1 ? captures1[1] : null;
    var charset2 = captures2 ? captures2[1] : null;

    var differ = false;
    if (charset1 && charset2) {
      if (charset1.toLowerCase() != charset2.toLowerCase())
        differ = true;
    }
    else if (charset1)
      differ = true;
    else if (charset2)
      differ = true;

    if (differ)
        cdump('charset differs: ' + doc.location.href + ' : charset1 = ' + charset1 + ', charset2 = ' + charset2);

    cdump('response headers defaultheader       ' + xhr1_responseheaders);
    cdump('response headers acceptcharsetheader ' + xhr2_responseheaders);

    cdump('response text    defaultheader       ' + xhr1_responsetext);
    cdump('response text    acceptcharsetheader ' + xhr2_responsetext);

    cdump('charset1 = ' + charset1);
    cdump('charset2 = ' + charset2);

  }
  catch(ex)
  {
    siteMessage(ex + '');
  }

  completePage();

}

function completePage()
{
  dlog('completePage()');

  gPageCompleted = true;
}


function userOnStop()
{
  dlog('userOnStop()');

}

function siteMessage(s)
{
  cdump('Site: ' + gURL + ': ' + s);
}
