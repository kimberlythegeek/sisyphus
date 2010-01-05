/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
 * top-sites user hook function to find use of moz-binding
 */

var gPageRandomWait = 10 * 3;

var gxhr = new XMLHttpRequest();

var gLoadedFiles = {};

function userOnStart()
{
  dlog('userOnStart()');
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
    processPage();
  }
  catch(ex)
  {
    cdump(ex + '');
  }

  var t = Math.random() * gPageRandomWait;
  setTimeout(completePage, Math.round(t));
}

function completePage()
{
  dlog('completePage()');
  // added in Spider 0.0.1.8
  // gc to flush out issues quickly
  collectGarbage();
  gPageCompleted = true;
}


function userOnStop()
{
  dlog('userOnStop()');
}

function processPage()
{
  var i;
  var source;

  var doc = gSpider.mDocument;

  dlog('processing location: ' + doc.location.href);

  var styles = doc.getElementsByTagName('style');

  for (i = 0; i < styles.length; i++)
  {
    var style = styles[i];

    if (processCSS(doc.location.href, style.innerHTML))
    {
      matchedMozBinding('-moz-binding: style', doc.location.href);
    }
  }

  var links = doc.getElementsByTagName('link');

  for (i = 0; i < links.length; i++)
  {
    var link = links[i];

    var type = link.getAttribute('type');
    var href = link.getAttribute('href');

    if (type && type.match(/text\/css/i))
    {
      dlog('processing link: type: ' + type + ' href: ' + href);

      href = absolutePath(doc.location.href, href);
     
      source = loadFile(href);

      if (source && processCSS(doc.location.href, source))
      {
        matchedMozBinding('-moz-binding: link', href);
      }
    }
  }

  var scripts = doc.getElementsByTagName('script');

  for (i = 0; i < scripts.length; i++)
  {
    var script   = scripts[i];
    var language = script.getAttribute('language');
    var type     = script.getAttribute('type');
    var src      = script.getAttribute('src');

    if ((!language && !type) || (language && language.match(/javascript/i)) || (type && type.match(/javascript/i)))
    {
      if (!src)
      {
        dlog('processing script inline: ' + doc.location.href);

        if (processJavaScript(script.innerHTML))
        {
          matchedMozBinding('MozBinding: script inline', doc.location.href);
        }
      }
      else
      {
        dlog('processing script src: ' + src + ' language: ' + language + ' type: ' + type);

        src = absolutePath(doc.location.href, src);

        source = loadFile(src);

        if (source && processJavaScript(source))
        {
          matchedMozBinding('MozBinding: script external', src);
        }
      }
    }
    else
    {
      cdump('skipping script src: ' + src + ' language: ' + language + ' type: ' + type);
    }
  }

  var elements = doc.getElementsByTagName('*');

  for (i = 0; i < elements.length; i++)
  {
    var element = elements[i];
    var attributes = element.attributes;

    for (var j = 0; j < attributes.length; j++)
    {
      var attribute = attributes.item(j);
      var name      = attribute.name.toLowerCase();
      var value     = attribute.value;

      if (!value)
      {
        continue;
      }

      if (name == 'style')
      {
        if (processCSS(doc.location.href, value))
        {
          matchedMozBinding('-moz-binding: style attr', doc.location.href);
        }
      }
      else if (/^on/i.exec(name))
      {
        if (processJavaScript(value))
        {
          matchedMozBinding('MozBinding: script ' + name, doc.location.href);
        }
      }
    }
  }
}

function processCSS(baseurl, css)
{
  var captures;

  dlog('processCSS(' + baseurl + ', ' + css + ')');

  var result = false;

  if (/\-moz-binding/m.exec(css))
  {
    result = true;
  }

  while (captures = /\@import *([^;]*)/gm.exec(css))
  {
    var url = captures[1];
    dlog('import: ' + url);

    url = url.replace(/\/\*.*\*\//g, '');
    url = url.replace(/url\(([^\)]*)\)/, '$1');
    url = url.replace(/"([^\"]*)"/, '$1');
    url = url.replace(/'([^\']*)'/, '$1');

    dlog('import url: ' + url);

    url = absolutePath(baseurl, url);

    var source = loadFile(url);

    dlog('response: ' + gxhr.responseText);

    if (source && processCSS(url, source))
    {
      // do this even if results is already true to find all matches
      matchedMozBinding('-moz-binding import', url);

      result = true;
    }
  }

  return result;
}

function processJavaScript(js)
{
  dlog('processJavaScript(' + js + ')');

  if (/MozBinding/m.exec(js))
  {
    return true;
  }
  return false;
}

/*
 * if path is not absolute, make is so relative
 * to href.
 */
function absolutePath(href, path)
{
  dlog('absolutePath(' + href + ', ' + path + ')');

  if (!/^http/i.exec(path) )
  {

    if (path.charAt(0) == '/')
    {
      base = href.replace(/(https?:\/\/[^\/]*).*/, "$1");
      dlog('base: ' + base);
    }
    else
    {
      var skip = 0;

      var skipregex = /\.\.\//g;
      while (skipregex.exec(path))
      {
        ++skip;
      }

      path = path.substring(skip * '../'.length);

      var locparts = href.split('/');
      var base = locparts.slice(0,locparts.length - skip - 1).join('/');

      if (base.charAt(base.length - 1) != '/')
      {
        base = base + '/';
      }

      if (path.charAt(0) == '/')
      {
        path = path.substring(1);
      }
    }
    path = base + path;
  }
  dlog('absolutePath: ' + path);
  return path;
}

function loadFile(url)
{
  dlog('loadFile(' + url + ')');

  if (gLoadedFiles[url])
  {
    dlog('loadFile(' + url + ') already loaded');
  }
  else
  {
    dlog('fetching ' + url);
    gLoadedFiles[url] = 1;
    gxhr.open('get', url, false);
    gxhr.send(null);
    return gxhr.responseText;
  }

  dlog('loadFile: ' + url + ' already processed');

  return '';
}

function matchedMozBinding(tag, url)
{
  cdump('MATCHED: ' + tag + ' : ' + url);
}
