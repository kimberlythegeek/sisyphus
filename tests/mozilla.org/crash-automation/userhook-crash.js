/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * top-sites user hook function 
 * report compatMode, script usage, object/embed usage
 * perform random page transition
 */

var gWaitAfterLoad = 5000;
var gObjectClassIds = {};
var gEmbedTypes = {};
var gMapClassIdType = {};

var gPageCount = 0;
var gPageLimit = 3;

function userOnStart()
{
  dlog('userOnStart()');
  gObjectClassIds = {};
  gEmbedTypes = {};
  gMapClassIdType = {};
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
      cdump('Spider: getting wrapped window object');
      win = win.wrappedJSObject;
    }

    var embedlist = win.document.getElementsByTagName('EMBED');

    if (embedlist.wrappedJSObject)
    {
      cdump('Spider: getting wrapped embedlist object');
      embedlist = embedlist.wrappedJSObject;
    }

    cdump('Spider: got ' + embedlist.length + ' embed elements');

    for (i = 0; i < embedlist.length; i++)
    {
      embed = embedlist[i];
      if (embed.wrappedJSObject)
      {
        cdump('Spider: getting wrapped embed object');
        embed = embed.wrappedJSObject;
      }
      if (/flash/i.exec(embed.type))
      {
        try {
          cdump("Spider: flash src=" + embed.src);
        }
        catch(ex) {
          cdump(ex);
        }
        try {
          cdump("Spider: flash TotalFrames=" + embed.TotalFrames());
        }
        catch(ex) {
          cdump(ex);
        }
        try {
          cdump("Spider: flash PecentLoaded=" + embed.PercentLoaded());
        }
        catch(ex) {
          cdump(ex);
        }
        try {
          cdump("Spider: flash IsPlaying=" + embed.IsPlaying());
        }
        catch(ex) {
          cdump(ex);
        }
        try {
          if (!embed.IsPlaying())
          {
            cdump("Spider: flash Play()");
            embed.Play();
          }
        }
        catch(ex)
        {
          cdump(ex);
        }
        try {
          cdump("Spider: SetVariable");
          embed.SetVariable("yoyodyne", "Lord Worphin");
        }
        catch(ex)
        {
          cdump(ex);
        }
        try {
          cdump("Spider: GetVariable " + embed.GetVariable("yoyodyne"));
        }
        catch(ex)
        {
          cdump(ex);
        }
      }
    }

    cdump('Spider: blur()');
    win.blur();
    cdump('Spider: focus()');
    win.focus();
    cdump('Spider: moveTo(1,1)');
    win.moveTo(1,1)
      cdump('Spider: resizeTo(0,0)');
    win.resizeTo(0, 0);
    cdump('Spider: resizeTo(' + screen.availWidth + ',' + screen.availHeight + ')');
    win.resizeTo(screen.availWidth,screen.availHeight);
    cdump('Spider: gc()');
    collectGarbage();

    var fundown = (function () { cdump("Spider: scrollByPages(1)");win.scrollByPages(1); });

    for (var i = 0; i < 3; i++)
    {
      win.setTimeout(fundown, i*1000);
    }

    var funup = (function () { cdump("Spider: scrollByPages(-1)");win.scrollByPages(-1); });

    for (i = 0; i < 3; i++)
    {
      win.setTimeout(funup, (3+i)*1000);
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

  if (gPageCount >= gPageLimit)
  {
    gSpider.stop();
  }

  gPageCompleted = true;

}


function compatModeOnAfterPage()
{
  dlog('compatModOnAfterPage()');

  siteMessage('Page: ' + 
        gSpider.mCurrentUrl.mUrl + 
        ' is in ' + 
        (gSpider.mDocument.compatMode == 'BackCompat' ? 
         'Quirks' : 'Standards') +
        ' mode.');
}

function userOnStop()
{
  dlog('userOnStop()');

  var val;
  var prefix;

  prefix = 'SITE_SUMMARY: ';

  siteMessage(prefix + 'OBJECT CLSID/DATA\n\n');

  for (val in gObjectClassIds)
  {
    siteMessage(prefix + val + ' occurred ' + gObjectClassIds[val] + ' times.');
  }

  siteMessage(prefix + 'Unique EMBED TYPE\n\n');

  for (val in gEmbedTypes)
  {
    siteMessage(prefix + val + ' occurred ' + gEmbedTypes[val] + ' times.');
  }
  
  siteMessage(prefix + 'CLASSID to TYPE map\n\n');

  for (val in gMapClassIdType)
  {
    siteMessage(prefix + 'CLASSID ' + val + ' == ' + 'TYPE ' + gMapClassIdType[val]);
  }
}

function objectsOnAfterPage()
{
  var i;
  var elm;
  var wmode;
  var doc = gSpider.mDocument;
  var loc = doc ? doc.location.href : '';
  var emblist;

  var reLanguageVer = /javascript([0-9.]*)/i;
  var scrlist = doc.getElementsByTagName('script');

  for (i = 0; i < scrlist.length; i++)
  {
    var scr = scrlist[i];

    var file = scr.getAttribute('src');

    if (scr.getAttribute('for') || scr.getAttribute('event'))
    {
      siteMessage('WARNING: SCRIPT FOR EVENT. Source File: ' + loc + 
            (file ? ' src: ' + file : ''));
    }
    // check for javascript language version uses which can cause
    // incompatibilities
    var scrLanguage = scr.getAttribute('language');
    var scrType = scr.getAttribute('type');
    if (scrLanguage)
    {
      siteMessage('SCRIPT: LANGUAGE ' + scrLanguage + ' ' +
            'TYPE ' + scrType + '. Source File: ' + loc + 
            (file ? ' src: ' + file : ''));
    }
  }

  var objlist = doc.getElementsByTagName('object');

  for (i = 0; i < objlist.length; i++)
  {
    elm   = objlist[i];
    var classid = elm.getAttribute('classid');
    var data  = elm.getAttribute('data');
    var paramList = elm.getElementsByTagName('param');
    for (var j = 0; j < paramList.length; j++)
    {
      var param = paramList[j];
      var name  = param.getAttribute('name');
      if (name)
      {
        name = name.toLowerCase();
        if (name == 'wmode')
        {
          wmode = param.getAttribute('value');
        }
      }
    }

    siteMessage('OBJECT: classid = ' + classid + ' ' + 
          (data ? 'data = ' + data  + ' ' : '') + 
          (wmode ? 'wmode = ' + wmode  + ' ' : '') + '. Source File: ' + loc );

    emblist = elm.getElementsByTagName('embed');
    if (emblist.length == 0)
    {
      siteMessage('WARNING: OBJECT Tag does not contain EMBED Tag. Source File: ' + 
            loc + (file ? ' src: ' + file : ''));
    }
    else
    {
      var emb = emblist[0];

      if (wmode)
      {
        var ewmode = emb.getAttribute('wmode');
        if (!ewmode)
        {
          siteMessage('WARNING: OBJECT Tag has FLASH WMODE ' + 
                'but child EMBED Tag does not. Source File: ' + loc + 
                (file ? ' src: ' + file : ''));
        }
      }

      var etype = emb.getAttribute('type');

      if (etype && classid)
      {
        classid = classid.toLowerCase();
        etype = etype.toLowerCase();
        gMapClassIdType[classid] = etype;
      }

      objectsDumpEmbed(emb, loc);
    }

    if (classid)
    {
      classid = classid.toLowerCase();

      if (classid in gObjectClassIds)
      {
        gObjectClassIds[classid] += 1;
      }
      else
      {
        gObjectClassIds[classid] = 1;
      }
    }

    if (data)
    {
      if (data in gObjectClassIds)
      {
        gObjectClassIds[data] += 1;
      }
      else
      {
        gObjectClassIds[data] = 0;
      }
    }
  }

  // dump embed tags not contained in object tags

  emblist = doc.getElementsByTagName('embed');
  for (i = 0; i < emblist.length; i++)
  {
    elm = emblist[i];
    var parent = elm.parentNode;
    if (parent && parent.tagName != 'OBJECT')
    {
      objectsDumpEmbed(elm, loc);
    }
  }
}


function objectsDumpEmbed(elm, loc)
{
  var src   = elm.getAttribute('src');
  var type  = elm.getAttribute('type');
  var wmode = elm.getAttribute('wmode');

  siteMessage('EMBED: type = ' + type + ' ' + 
        (wmode ? 'wmode = ' + wmode  + ' ' : '') + '. Source File: ' + loc );

  if (type)
  {
    type = type.toLowerCase();

    if (type in gEmbedTypes)
    {
      gEmbedTypes[type] += 1;
    }
    else
    {
      gEmbedTypes[type] = 1;
    }
  }
}

function siteMessage(s)
{
  cdump('Site: ' + gURL + ': ' + s);
}
