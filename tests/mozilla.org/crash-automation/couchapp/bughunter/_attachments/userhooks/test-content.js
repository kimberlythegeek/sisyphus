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
var gPageLimit = 1;

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

  completePage();
  return;

  try
  {
    var win = gSpider.mDocument.defaultView;
    if (win.wrappedJSObject)
    {
      cdump('Spider: getting wrapped window object');
      win = win.wrappedJSObject;
    }
  }
  catch(ex)
  {
    siteMessage(ex + '');
  }

  var embedlist = win.document.getElementsByTagName('EMBED');

  if (embedlist.wrappedJSObject)
  {
    cdump('Spider: getting wrapped embedlist object');
    embedlist = embedlist.wrappedJSObject;
  }

  cdump('Spider: got ' + embedlist.length + ' embed elements');

  var objectlist = win.document.getElementsByTagName('OBJECT');

  if (objectlist.wrappedJSObject)
  {
    cdump('Spider: getting wrapped objectlist object');
    objectlist = objectlist.wrappedJSObject;
  }

  cdump('Spider: got ' + objectlist.length + ' object elements');

  gPluginList = [];

  for (var i = 0; i < embedlist.length; i++)
    gPluginList.push(embedlist[i]);

  for (i = 0; i < objectlist.length; i++)
    gPluginList.push(objectlist[i]);

  setTimeout(exerciseFlash, gWaitAfterLoad);

}

var gPluginList;
var gFlashAttempts = 0;
var gFlashAttemptsMax = 10;

function exerciseFlash()
{

  var flashmimetype = navigator.mimeTypes["application/x-shockwave-flash"];

  if (!flashmimetype || !flashmimetype.enabledPlugin)
  {
    cdump('Spider: exerciseFlash: Flash not available');
  }
  else
  {
    for (var i = 0; i < gPluginList.length; i++)
    {
      var plugin = gPluginList[i];
      if (plugin.wrappedJSObject)
      {
        cdump('Spider: getting wrapped plugin');
        plugin = plugin.wrappedJSObject;
      }
      if (/flash/i.exec(plugin.type))
      {
        try {
          cdump("Spider: flash PecentLoaded=" + plugin.PercentLoaded());
        }
        catch(ex) {
          if (++gFlashAttempts > gFlashAttemptsMax)
          {
            cdump('Spider: *** FLASH ERROR *** exerciseFlash exceeded maximum attempts: ' + ex);
            //completePage();
            exerciseContent();
          }
          else
          {
            setTimeout(exerciseFlash, 1000);
          }
          return;
        }

      }
    }

    for (var i = 0; i < gPluginList.length; i++)
    {
      var plugin = gPluginList[i];
      if (plugin.wrappedJSObject)
      {
        cdump('Spider: getting wrapped plugin');
        plugin = plugin.wrappedJSObject;
      }
      if (/flash/i.exec(plugin.type))
      {
        cdump('Spider: flash ' + plugin.nodeName);

        try {
          cdump("Spider: flash TotalFrames=" + plugin.TotalFrames());
        }
        catch(ex) {
          cdump('Spider: flash TotalFrames=' + ex);
        }

        try {
          cdump("Spider: flash PecentLoaded=" + plugin.PercentLoaded());
        }
        catch(ex) {
          cdump("Spider: flash PecentLoaded=" + ex);
        }

        var isplaying;

        try {
          isplaying = plugin.IsPlaying();
          cdump("Spider: flash IsPlaying=" + isplaying);
        }
        catch(ex) {
          cdump("Spider: flash IsPlaying=" + ex);
        }

        if (isplaying)
        {
          try {
            cdump("Spider: flash StopPlay()");
            plugin.StopPlay();
            try {
              isplaying = plugin.IsPlaying();
              cdump("Spider: flash IsPlaying=" + isplaying);
            }
            catch(ex) {
              cdump("Spider: flash IsPlaying=" + ex);
            }
          }
          catch(ex)
          {
            cdump("Spider: flash StopPlay()" + ex);
          }
        }

        if (!isplaying)
        {
          try {
            cdump("Spider: flash Play()");
            plugin.Play();
          }
          catch(ex)
          {
            cdump("Spider: flash Play()" + ex);
          }
        }

        try {
          isplaying = plugin.IsPlaying();
          cdump("Spider: flash IsPlaying=" + isplaying);
        }
        catch(ex) {
          cdump("Spider: flash IsPlaying=" + ex);
        }

        if (!isplaying)
        {
          cdump('Spider: *** FLASH ERROR *** Flash should be playing but is not.');
        }

        try {
          cdump("Spider: flash SetVariable");
          plugin.SetVariable("yoyodyne", "Lord Worphin");
        }
        catch(ex)
        {
          cdump("Spider: flash SetVariable" + ex);
        }

        try {
          cdump("Spider: flash GetVariable " + plugin.GetVariable("yoyodyne"));
        }
        catch(ex)
        {
          cdump("Spider: flash GetVariable " + ex);
        }


        var flashvariables = {}
        var flashvarsattr;

        var attributes = plugin.attributes;
        for (var iattr = 0; iattr < attributes.length; iattr++)
        {
          flashvariables[attributes[iattr].name] = attributes[iattr].value;
        }

        flashvarsattr = plugin.getAttribute('flashvars');
        if (!flashvarsattr && /object/i.exec(plugin.nodeName))
        {
          var paramlist = plugin.getElementsByTagName('param');
          for (var iparam = 0; iparam < paramlist.length; iparam++)
          {
            if (/flashvars/i.exec(paramlist[iparam].name))
            {
              flashvarsattr = paramlist[iparam].value;
              break;
            }
          }
        }

        if (flashvarsattr)
        {
          cdump("Spider: flash flashvars=" + flashvarsattr);
          var namevaluelist = flashvarsattr.split('&');
          for (var inamevalue = 0; inamevalue < namevaluelist.length; inamevalue++)
          {
            var namevaluepair = namevaluelist[inamevalue].split('=');
            if (namevaluepair.length == 1)
              flashvariables[namevaluepair[0]] = '';
            else
              flashvariables[namevaluepair[0]] = namevaluepair[1];
          }
        }

        for (var varname in flashvariables)
        {
          cdump('Spider: flash var ' + varname + '=' + flashvariables[varname]);

          try {
            var varvalue = plugin[varname];
            if (varvalue)
              cdump('Spider: flash attribute ' + varname + ' value ' + varvalue);
            else {
              varvalue = plugin.GetVariable(varname);
              if (varvalue)
                cdump('Spider: flash variable ' + varname + ' value ' + varvalue);
            }
          }
          catch(ex)
          {
            cdump(ex);
          }
        }

      }
    }
  }
  //completePage();
  exerciseContent();
}

function injectScript(win, code)
{
  cdump('Spider: action: ' + code);
  var scriptelm = win.document.createElement('script');
  var textnode  = win.document.createTextNode(code);
  scriptelm.appendChild(textnode);
  if (win.document.body)
    win.document.body.appendChild(scriptelm);
}

function exerciseContent()
{

  try
  {
    var win = gSpider.mDocument.defaultView;
    if (win.wrappedJSObject)
    {
      cdump('Spider: getting wrapped window object');
      win = win.wrappedJSObject;
    }
    var winurl = win.document.location.href;

    var percent;
    cdump('Spider: resizeTo(0,0)');
    for (percent = 100; percent > 0; percent -= 5)
      win.resizeTo(percent*screen.availWidth/100, percent*screen.availHeight/100);

    cdump('Spider: resizeTo(' + screen.availWidth + ',' + screen.availHeight + ')');
    for (percent = 0; percent <= 100; percent += 5)
      win.resizeTo(percent*screen.availWidth/100, percent*screen.availHeight/100);

    cdump('Spider: gc()');
    collectGarbage();

    for (var i = 0; i < 3; i++)
    {
      injectScript(win, 'window.scrollByPages(1);');
    }

    for (i = 0; i < 3; i++)
    {
      injectScript(win, 'window.scrollByPages(-1);');
    }

    for (var prop in win)
    {
      var newwin = gSpider.mDocument.defaultView;
      if (newwin.wrappedJSObject)
      {
        newwin = newwin.wrappedJSObject;
      }

      if (winurl != newwin.document.location.href) {
        cdump('Spider: Content: something changed our location from ' + winurl + ' to ' + newwin.document.location.href + ' resetting...');
        win.location.href = winurl;
      }
      if (typeof win[prop] == 'function' && ! /resizeTo|scrollByPages|alert|confirm|prompt|dialog|print|home|forward|back|stop|close/i.exec(win[prop].toSource())) {
        var args = new Array(win[prop].arity);
        for (var iargs = 0; iargs < args.length; iargs++)
          args[iargs] = iargs + 1;
        var source = prop + '(' + args + ')';
        injectScript(win, source);
      }
    }
  }
  catch(ex)
  {
    siteMessage(ex + '');
  }

  cdump('Spider: gc()');
  collectGarbage();

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
