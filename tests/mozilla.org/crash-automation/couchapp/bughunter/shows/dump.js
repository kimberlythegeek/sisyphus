function(doc, req) {

  function dumpObject(object) {
    if (!object || typeof object != 'object')
      return object;
    s = '<ul>';
    for (var prop in object) {
      s += '<li>' + prop + '=' + dumpObject(object[prop]) + '</li>';
    }
    s += '</ul>';
    return s;
  }

  send('<h2>request properties</h2>')
  send(dumpObject(req));

  send('<h2>doc properties</h2>')
  send(dumpObject(doc));
};
