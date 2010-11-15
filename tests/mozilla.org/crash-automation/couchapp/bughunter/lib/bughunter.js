/*
 * htmlbuffer is used to collect strings of html
 * which will be sent to the client in a single batch.
 *
 * html = new htmlbuffer();
 * html.push('...');
 * html.push('...');
 * html.send();
 */
function htmlbuffer() {
  this._buffer = [];

  this.push = function (chunk) {
    this._buffer.push(chunk);
  };

  this.send = function () {
    send(this._buffer.join('\n') + '\n');
    this._buffer = [];
  };

}

/*
 * Create a set of links which perform a segmented search
 * into the specified list for the given set of keys.
 * Example:
 * segmented_key_search('history', 'list', 'assertion', {key1:'key1', key2:'key2'})
 * <a title='Search history by key1' href='list?include_docs=true&startkey=["assertion", "key1"]&endkey=["assertion", "key1", {}]'>key1</a>
 * <a title='Search history by key1,key2' href='list?include_docs=true&startkey=["assertion", "key1", "key2"]&endkey=["assertion", "key1", "key2", {}]'>key2</a>
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
    endkey.push({});

    var link = '<a title=\'' + partialsearchtitle + '\' href=\'' +
      list + '?include_docs=true' +
      '&startkey=' + startkey.toSource().replace(/'/g, escape("'")) +
      '&endkey=' + endkey.toSource().replace(/'/g, escape("'")) + '\'>' +
      escape_html(keyvalues[partialkeyend - 1]) + '<\/a>';

    links.push(link);

  }

  s = links.join(' ');

  return s;
}

function attachments_to_html(docid, attachments) {

  var s = '';
  var k = 1024;
  var attachment_list = [];
  var filename;
  var size;

  for (filename in attachments)
    attachment_list.push({filename: filename, size: (parseInt(100*attachments[filename].length/k)/100 + 'K')});

  attachment_list.sort();

  for (var i = 0; i < attachment_list.length; i++) {
    filename = attachment_list[i].filename;
    size     = attachment_list[i].size;
    s += '<li><a href="../../../../' + docid + '/' + filename + '">' + filename + ' (' + size + ')</a></li>';
  }

  if (s)
    s = '<ul>' + s + '</ul>';

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

function location_id_list_to_links(location_id_list) {
  var s = '<ol>';
  for (var i = 0; i < location_id_list.length; i++) {
    if (location_id_list[i] != 'head')
      s += '<li><a href="' + location_id_list[i] + '">' +
      escape_html(location_id_list[i]) + '<\/a></li>';
  }
  s += '<\/ol>';
  return s;
}

function escape_html(str) {
  function escape_html_char(c) {
    if (c == '<')
      return '&lt;';
    if (c == '>')
      return '&gt;';
    if (c == '&')
      return '&amp;';

    return c;
  }

  return str.replace(/[<>&]/g, escape_html_char);
}