function(head, req) {
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code lib/bughunter.js

  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // their priority. In this case HTML is the preferred format, so it comes first.
  provides("html", function() {

    var html = new htmlbuffer();
    var app_path = assetPath();

    html.push('<!DOCTYPE html>');
    html.push('<html>');
    html.push('  <head>');
    html.push('    <title>Assertion History - Bug Hunter</title>');
    html.push('    <link rel="stylesheet" href="' + app_path + '"style/main.css" type="text/css"/>');
    html.push('    <script src="/_utils/script/json2.js" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/sha1.js" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.js?1.4.2" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.couch.js?1.0.0" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.dialog.js?1.0.0" type="text/javascript"></script>');
    html.push('    <link href="' + app_path + '"script/jquery-ui/css/jquery-ui-1.8.2.custom.css" rel="stylesheet" type="text/css"/>');
    html.push('    <script src="' + app_path + '"script/jquery-ui/js/jquery-ui-1.8.2.custom.min.js" type="text/javascript"></script>');
    html.push('    <script src="' + app_path + '"script/application.js" type="text/javascript"></script>');
    html.push('  </head>');
    html.push('  <body>');
    html.push('    <div id="wrap">');

    html.push('      <h1>Assertion History</h1>');

    html.push('      <div id="content">');
    html.push('        <div id="toolbar">');
    html.push('          <span id="filter_display"><span id="filter_text"></span> <button type="button" id="modify_filter">Modify Filter</button></span>');
    html.push('        </div>');

    html.push('        <table>');
    html.send();
    var row, key;
    while ((row = getRow())) {

      var doc = row.doc;
      if (!doc)
        continue;

      var location_id_list_links = '';

      if ('location_id_list' in doc)
        location_id_list_links = location_id_list_to_links(doc.location_id_list);

      var bug_list = doc.bug_list;

      if (!bug_list || ! 'open' in bug_list || ! 'closed' in bug_list) {
        bug_list = {open : [], closed : []};
      }

      var segmented_search =
        segmented_key_search('results',
                             listPath() + '/result_assertions/crash_type/results',
                             'result_assertion',
                             {
                               assertion    : doc.assertion,
                               assertionfile: doc.assertionfile,
                               product      : doc.product,
                               branch       : doc.branch,
                               buildtype    : doc.buildtype,
                               os_name      : doc.os_name,
                               os_version   : doc.os_version,
                               cpu_name     : doc.cpu_name
                             });

      var open_bugs  = bug_list.open.join(', ');
      var closed_bugs = bug_list.closed.join(', ');

      html.push('<tr>');
      html.push('<td>Assertion</td>');
      html.push('<td>');
      html.push(segmented_search);
      html.push('</td>');
      html.push('</tr>');
      html.push('');
      html.push('<tr>');
      html.push('<td>');
      html.push('Date range');
      html.push('</td>');
      html.push('<td>');
      html.push(doc.firstdatetime + ' to ' + doc.lastdatetime);
      html.push('</td>');
      html.push('</tr>');
      html.push('');
      html.push('<tr>');
      html.push('<td>');
      html.push('urls');
      html.push('</td>');
      html.push('<td>');
      html.push(location_id_list_links);
      html.push('</td>');
      html.push('</tr>');
      html.push('');
      if (open_bugs) {
        html.push('<tr>');
        html.push('<td>');
        html.push('Open bugs');
        html.push('</td>');
        html.push('<td>');
        html.push('<a href="https://bugzilla.mozilla.org/buglist.cgi?bugidtype=include&query_format=advanced&bug_id=' + open_bugs + '">' + open_bugs + '</a>');
        html.push('</td>');
        html.push('</tr>');
      }
      html.push('');
      if (close_bugs) {
        html.push('<tr>');
        html.push('<td>');
        html.push('Closed bugs');
        html.push('</td>');
        html.push('<td>');
        html.push('<a href="https://bugzilla.mozilla.org/buglist.cgi?bugidtype=include&query_format=advanced&bug_id=' + closed_bugs + '">' + closed_bugs + '</a>');
        html.push('</td>');
        html.push('</tr>');
      }
      html.send();
    }

    html.push('</table>');
    html.push('</div> <!-- content -->');
    html.push('</div> <!-- wrap -->');
    html.push('</body>');
    html.push('</html>');
    html.send();

  });
};
