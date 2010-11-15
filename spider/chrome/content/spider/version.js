/* -*- Mode: C++; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*- */

/*
  place a call to sayVersion() in the onload handler or after an html
  div with id="version" to output the version string.
*/

var _version = '0.0.3.2';
var _date = 'August 30, 2010'

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
