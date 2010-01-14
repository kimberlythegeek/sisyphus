var bugzillaRESTUrl = 'https://api-dev.bugzilla.mozilla.org/stage/0.4';

function formatDate(date) {
  return date.toUTCString();
}

function differenceString(date1, date2) {
  var years = date2.getFullYear() - date1.getFullYear();
  var months = (years * 12) + date2.getMonth() - date1.getMonth();
  if(months > 1)
    return months + " months";
  var days = (months * 30) + date2.getDate() - date1.getDate();
  if(days > 1)
    return days + " days";
  var hours = (days * 24) + date2.getHours() - date1.getHours();
  if(hours > 0)
    return hours + " hours";
  var minutes = (hours * 60) + date2.getMinutes() - date1.getMinutes();
  return minutes + " minutes";
}

function getOSName(os, version) {
  /* get Bugzilla OS string */
  if(os == 'Windows NT') {
    switch(version) {
      case '6.1':
        return 'Windows 7';
      case '6.0':
        return 'Windows Vista';
      case '5.1':
        return 'Windows XP';
      case '5.2':
        return 'Windows Server 2003';
      default:
        return 'Windows ' + version; 
    }
  }
  return os + " " + version;
}

function getMajorVersion(versionString) {
  return parseInt(versionString.substring(0,2)) + '.' + parseInt(versionString.substring(2,4));
}

function getGeckoBranch(branch) {
  /* get Bugzilla branch string */
  switch(branch) {
    case '1.9.3': case '3.7':
      return 'Trunk';
    case '1.9.2': case '3.6':
      return '1.9.2 Branch';
    case '1.9.1': case '3.5':
      return '1.9.1 Branch';
    case '1.9.0': case '3.0':
      return '1.9.0 Branch';
    default:
      return 'unspecified';
  }
}

/* jQuery does some kind of timeout thing that doesn't work with the Bugzilla REST API */
function postJSON(url, data, callback, errback) {
  var req = new XMLHttpRequest();
  req.open("POST", url, true);
  req.setRequestHeader("Content-type", "application/json");
  req.setRequestHeader('Accept','application/json');
  req.setRequestHeader("Content-length", data.length);
  req.onreadystatechange = function (event) {
    if (req.readyState == 4) {
      if(req.status >= 200 && req.status < 300)
        callback(JSON.parse(req.responseText));
      else if(errback)
        errback(req);
    } 
  };
  req.send(data);
}

function putJSON(url, data, callback, errback) {
  var req = new XMLHttpRequest();
  req.open("PUT", url, true);
  req.setRequestHeader("Content-type", "application/json");
  req.setRequestHeader('Accept','application/json');
  req.setRequestHeader('Content-type', 'application/json');
  req.setRequestHeader("Content-length", data.length);
  req.onreadystatechange = function (event) {
    if (req.readyState == 4) {
      if(req.status >= 200 && req.status < 300)
        callback(JSON.parse(req.responseText));
      else if(errback)
        errback(req);
    } 
  };
  req.send(data);
}
  
function getJSON(url, callback, errback) {
  var req = new XMLHttpRequest();
  req.open('GET', url, true);
  req.onreadystatechange = function (event) {
    if (req.readyState == 4) {
      if(req.status >= 200 && req.status < 300)
        callback(JSON.parse(req.responseText));
      else if(errback)
        errback(req);
    } 
  };
  req.setRequestHeader('Content-Type', 'application/json');
  req.send(null);
}

function bugUrl(id) {
  return "http://bugzilla.mozilla.org/show_bug.cgi?id=" + id;
}
