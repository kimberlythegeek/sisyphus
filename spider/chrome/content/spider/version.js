/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
  place a call to sayVersion() in the onload handler or after an html
  div with id="version" to output the version string.
*/

var _version = '0.0.2.24';
var _date = 'May 29, 2010'

  function sayVersion()
{
  var version = document.getElementById('version');
  while (version.firstChild)
  {
    version.removeChild(version.firstChild);
  }
  version.appendChild(
    document.createTextNode('Spider ' +
                            _version  +
                            ' ' + _date));
}
