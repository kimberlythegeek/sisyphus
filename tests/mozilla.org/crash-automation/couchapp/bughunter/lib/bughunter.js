/*
 * Create a set of links which perform a segmented search
 * into the specified list for the given set of keys.
 * Example:
 * segmented_key_search('history', 'list', 'assertion', {key1:'key1', key2:'key2'})
 * <a title='Search history by key1' href='list?include_docs=true&startkey=["assertion", "key1"]&endkey=["assertion", "key1\u9999"]'>key1</a>
 * <a title='Search history by key1,key2' href='list?include_docs=true&startkey=["assertion", "key1", "key2"]&endkey=["assertion", "key1", "key2\u9999"]'>key2</a>
 */
function segmented_key_search(dbname, list, type, keyhash)
{
  var s = '';

  var keynames = [];
  var keyvalues = [];
  for (keyname in keyhash) {
    keynames.push(keyname);
    keyvalues.push(keyhash[keyname]);
  }

  var links = [];
  for (var partialkeyend = 1; partialkeyend <= keynames.length; partialkeyend++)
  {
    var partialsearchtitle = 'Search ' + dbname + ' by ' +
      keynames.slice(0, partialkeyend).join(', ');

    var startkey = [encodeURIComponent(type)];
    for (var ikey = 0; ikey < partialkeyend; ikey++)
    {
      startkey.push(encodeURIComponent(keyvalues[ikey].replace(/"/g, '\\"')));
    }
    var endkey   = startkey.slice(0);
    endkey[endkey.length-1] += '\u9999';

    var link = '<a title=\'' + partialsearchtitle + '\' href=\'' +
      list + '?include_docs=true' +
      '&startkey=' + startkey.toSource().replace(/'/g, escape("'")) +
      '&endkey=' + endkey.toSource().replace(/'/g, escape("'")) + '\'>' +
      keyvalues[partialkeyend - 1] + '<\/a>';

    links.push(link);

  }

  s = links.join(' ');

  return s;
}

function attachments_to_html(doc) {
  var s = '';
  var attachment_list = [];
  for (var filename in doc._attachments) {
    attachment_list.push(filename);
  }
  attachment_list.sort();
  for (var i = 0; i < attachment_list.length; i++) {
    filename = attachment_list[i];
    s += '<li><a href="../../../../' + doc._id + '/' + filename + '">' + filename + '</a></li>';
  }
  if (s) {
    s = '<ul>' + s + '</ul>';
  }
  return s;
}

function steps_to_html(steps) {
  if (!steps)
    return 'No steps found.';

  var s = '';
  for (var i = 0; i < steps.length; i++) {
    s += '<li>' + steps[i] + '</li>';
  }
  if (s) {
    s = '<ol>' + s + '</ol>';
  }
  return s;
}


function extra_to_html(extra) {
  if (!extra)
    return 'No extra data found.';

  var s = '<ul>';
  for (var prop in extra) {
    s += '<li>' + prop + ' = ' + extra[prop] + '<\/a></li>';
  }
  s += '<\/ul>';
  return s;
}

