/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * top-sites user hook function 
 * report css font-face downloadable font url
 */

var gWaitAfterLoad = 0 * 1000;

var gPageCount = 0;
var gPageLimit = 1;

function userOnStart()
{
  dlog('userOnStart()');
  gURL = gForm.url.value;
}

function userOnBeforePage()
{
  dlog('userOnBeforePage()');

  if (gPageCount >= gPageLimit)
  {
    gSpider.stop();
  }

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

    var styleSheetList = doc.styleSheets;
    for (var isheet = 0; isheet < styleSheetList.length; isheet++)
    {
      styleSheet = styleSheetList[isheet];
      for (var irule = 0; irule < styleSheet.cssRules.length; irule++)
      {
        cssRule = styleSheet.cssRules[irule];
        if (cssRule.type == CSSRule.FONT_FACE_RULE)
        {
          var src = cssRule.style.getPropertyValue('src');
          siteMessage('font-face-src=' + src);
        }
      }
    }
  }
  catch(ex)
  {
    siteMessage(ex + '');
  }

  setTimeout(completePage, gWaitAfterLoad);

}

function completePage()
{
  dlog('completePage()');

  ++gPageCount;

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
