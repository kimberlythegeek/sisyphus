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
var gPageLimit = 10;

function injectScript(win, code)
{
  if (!win.document.body)
    return;
  cdump('Spider: <script>');
  var scriptelm = win.document.createElement('script');
  var lines = code.split('\n');
  for (var iline = 0; iline < lines.length; iline++) {
    cdump(lines[iline]);
    var textnode  = win.document.createTextNode(lines[iline] + '\n');
    scriptelm.appendChild(textnode);
  }
  cdump('<\/script>');
  win.document.body.appendChild(scriptelm);
}

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

  setTimeout(exerciseContent, gWaitAfterLoad);
}

function exerciseContent()
{
  try
  {
    var win = gSpider.mDocument.defaultView;
    if (win.wrappedJSObject)
    {
      win = win.wrappedJSObject;
    }
    var winurl = win.document.location.href;

    var source = '' +
      'var percent;\n' +
      'for (percent = 100; percent  >   0; percent -= 5) window.resizeTo(percent*screen.availWidth/100, percent*screen.availHeight/100);\n' +
      'for (percent =   0; percent <= 100; percent += 5) window.resizeTo(percent*screen.availWidth/100, percent*screen.availHeight/100);\n' +
      'for (var i = 0; i < 3; i++) window.scrollByPages(1);\n' +
      'for (i = 0; i < 3; i++) window.scrollByPages(-1);\n';

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
        var args = new Array(win[prop].length);
        for (var iargs = 0; iargs < args.length; iargs++)
          args[iargs] = (iargs + 1)+'';
        // convert args array into (arg1,..)
        args = args.toSource().replace(/[\[\]]/g, '').replace(/\"/g, '\'');
        source += 'try { ' + prop + '(' + args + '); } catch(ex) { dump("' + prop + '(' + args + '): " + ex + "\\n"); }\n';
      }
    }
  }
  catch(ex)
  {
    siteMessage(ex + '');
  }

  var flashmimetype = navigator.mimeTypes["application/x-shockwave-flash"];

  if (flashmimetype && flashmimetype.enabledPlugin)
  {
    source +=
      'var embedlist = window.document.getElementsByTagName("EMBED");\n' +
      'dump("Spider: found " + embedlist.length + " embed elements\\n");\n' +
      'var objectlist = window.document.getElementsByTagName("OBJECT");\n' +
      'dump("Spider: found " + objectlist.length + " object elements\\n");\n' +
      'plugin_list = [];\n' +
      'for (var i = 0; i < embedlist.length; i++) plugin_list.push(embedlist[i]);\n' +
      'for (i = 0; i < objectlist.length; i++) plugin_list.push(objectlist[i]);\n' +
      'for (var i = 0; i < plugin_list.length; i++) {\n' +
      '    var plugin = plugin_list[i];\n' +
      '    if (/flash/i.exec(plugin.type)) {\n' +
      '        dump("Spider: flash plugin.nodeName = " + plugin.nodeName + "\\n");\n' +
      '        try { dump("Spider: plugin.TotalFrames()  = " + plugin.TotalFrames() + "\\n"); }   catch(ex) { dump("Spider: plugin.TotalFrames() :" + ex + "\\n"); }\n' +
      '        try { dump("Spider: plugin.PecentLoaded() = " + plugin.PercentLoaded() + "\\n"); } catch(ex) { dump("Spider: plugin.PecentLoaded():" + ex + "\\n"); }\n' +
      '        try { dump("Spider: plugin.IsPlaying()    = " + plugin.IsPlaying() + "\\n"); }     catch(ex) { dump("Spider: plugin.IsPlaying()   :" + ex + "\\n"); }\n' +
      '        try { if (plugin.IsPlaying()) plugin.StopPlay(); } catch(ex) { dump("Spider: plugin.StopPlay(): " + ex + "\\n");  }\n' +
      '        try { if (!plugin.IsPlaying()) plugin.Play(); } catch(ex) { dump("Spider: plugin.Play(): " + ex + "\\n");  }\n' +
      '        try { dump("Spider: plugin.IsPlaying() =" + plugin.IsPlaying() + "\\n"); } catch(ex) { dump("Spider: plugin.IsPlaying(): " + ex + "\\n"); }\n' +
      '        try { plugin.SetVariable("yoyodyne", "Lord Worphin"); } catch(ex) { dump("Spider: plugin.SetVariable(\'yoyodyne\', \'Lord Worphin\'): " + ex + "\\n"); }\n' +
      '        try { dump("Spider: plugin.GetVariable(\'yoyodyne\') = " + plugin.GetVariable("yoyodyne") + "\\n"); } catch(ex) { dump("Spider: plugin.GetVariable(\'yoyodyne\'): " + ex + "\\n"); }\n';
/*
    var flashvariables = {}
    var flashvarsattr;

    var attributes = plugin.attributes;
    for (var iattr = 0; iattr < attributes.length; iattr++)
    {
      flashvariables[attributes[iattr].name] = attributes[iattr].value;
    }

    flashvarsattr = plugin.getAttribute("flashvars");
    if (!flashvarsattr && /object/i.exec(plugin.nodeName))
    {
      var paramlist = plugin.getElementsByTagName("param");
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
      dump("Spider: flash flashvars=" + flashvarsattr);
      var namevaluelist = flashvarsattr.split("&");
      for (var inamevalue = 0; inamevalue < namevaluelist.length; inamevalue++)
      {
        var namevaluepair = namevaluelist[inamevalue].split("=");
        if (namevaluepair.length == 1)
          flashvariables[namevaluepair[0]] = "";
        else
          flashvariables[namevaluepair[0]] = namevaluepair[1];
      }
    }

    for (var varname in flashvariables)
    {
      dump("Spider: flash var " + varname + "=" + flashvariables[varname]);

      try {
        var varvalue = plugin[varname];
        if (varvalue)
          dump("Spider: flash attribute " + varname + " value " + varvalue);
        else {
          varvalue = plugin.GetVariable(varname);
          if (varvalue)
            dump("Spider: flash variable " + varname + " value " + varvalue);
        }
      }
      catch(ex)
      {
        dump(ex);
      }
    }
*/
    source +=  '    }\n';
    source +=  '}\n';
  }
  injectScript(win, source);

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
