/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
  place a call to sayVersion() in the onload handler or after an html
  div with id="version" to output the version string.
*/

var _version = '0.1.0.3';
var _date = 'December 30, 2015';

function sayVersion()
{
  var rv      = '';
  var version = document.getElementById('version');
  var rvmatch = navigator.userAgent.match(/rv:([\w.]*)/);
  if (rvmatch && rvmatch.length >= 2)
    rv = rvmatch[1];

  while (version.firstChild)
  {
    version.removeChild(version.firstChild);
  }
  version.appendChild(
    document.createTextNode('Spider/' + _version + ' ' + _date + ' rv:' + rv + ' ' + navigator.buildID)
    );
}
