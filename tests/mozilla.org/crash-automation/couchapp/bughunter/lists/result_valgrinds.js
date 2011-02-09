function(head, req) {
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code lib/bughunter.js

  var key_options = {name:  'Valgrind', field: 'valgrindsignature'};

  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // their priority. In this case HTML is the preferred format, so it comes first.
  provides("html", function() {

    var html = new htmlbuffer();
    var app_path = assetPath();
    var list_path = listPath();

    var filter = {};

    if (req.query.filter) {
      try {
        filter = JSON.parse(req.query.filter);
      }
      catch (ex) {
        send('Error parsing filter: ' + ex);
      }
    }

    html.push('<!DOCTYPE html>');
    html.push('<html>');
    html.push('  <head>');
    html.push('  <title>Crash Test Valgrind - Bug Hunter</title>');
    html.push('    <link rel="stylesheet" href="' + app_path + '/style/main.css" type="text/css"/>');
    html.push('    <script src="/_utils/script/json2.js" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/sha1.js" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.js?1.4.2" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.couch.js?1.0.0" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.dialog.js?1.0.0" type="text/javascript"></script>');
    html.push('    <script src="' + app_path + '/script/application.js" type="text/javascript"></script>');

    html.push('    <link href="' + app_path + '/script/jquery-ui/css/jquery-ui-1.8.2.custom.css" rel="stylesheet" type="text/css"/>');
    html.push('    <script src="' + app_path + '/script/jquery-ui/js/jquery-ui-1.8.2.custom.min.js" type="text/javascript"></script>');

    // Must define key_options before including script/date-field-branch-os-filter.js
    html.push('    <script type="text/javascript">');
    html.push('      var key_options = ' + JSON.stringify(key_options) + ';');
    html.push('    </script>');
    html.push('    <script src="' + app_path + '/script/date-field-branch-os-filter.js" type="text/javascript"></script>');
    html.push('  </head>');
    html.push('  <body>');
    html.push('');
    html.push('  <div id="wrap">');
    html.push('');
    html.push('  <h1>Valgrind Results</h1>');
    html.push('      <div id="content">');
    html.push('        <div id="toolbar">');
    html.push('          <span id="filter_display"><span id="filter_text"></span> <button type="button" id="modify_filter">Modify Filter</button></span>');
    html.push('        </div>');
    html.send();

    html.push('<table>');

    var row, key;
    var stop = false;

    while ((row = getRow())) {

      var doc = row.doc;
      if (!doc)
        continue;

      var keep = true;

      if (filter) {

        // check impossible conditions first
        if (filter.start_date > filter.end_date)
          stop = true;
        else if (filter.start_date_type == 'before' && filter.end_date_type == 'notbefore')
          stop = true;
        else if (filter.start_date_type == 'notafter' && filter.end_date_type == 'after')
          stop = true;
        else if (filter.start_date_type == 'notafter' && filter.end_date_type == 'notbefore')
          stop = true;

        if (stop)
          break;

        for each (var date_name in ['start_date', 'end_date']) {

          if (!keep)
            break;

          var date_type = date_name + '_type';

          if (filter[date_type] == 'before' &&
              !(doc.datetime < filter[date_name]))
            keep = false;
          else if (filter[date_type] == 'after' &&
                   !(doc.datetime > filter[date_name]))
            keep = false;
          else if (filter[date_type] == 'notbefore' &&
                   (doc.datetime < filter[date_name]))
            keep = false;
          else if (filter[date_type] == 'notafter' &&
                   (doc.datetime > filter[date_name]))
            keep = false;

        }

        if (filter.field && !RegExp(filter.field, "i").test(doc[key_options.field]))
          keep = false;

        if (filter.branches && !RegExp(filter.branches).test(doc.branch))
          keep = false;

        if (filter.os && !RegExp(filter.os).test(doc.os_name))
          keep = false;

        if (!keep)
          continue;
      }

      var segmented_search =
        segmented_key_search('history',
                             listPath() + '/history_valgrinds_summary/crash_type/results',
                             'history_valgrind',
                             {
                               valgrind    : doc.valgrind,
                               valgrindsignature: doc.valgrindsignature,
                               product      : doc.product,
                               branch       : doc.branch,
                               buildtype    : doc.buildtype,
                               os_name      : doc.os_name,
                               os_version   : doc.os_version,
                               cpu_name     : doc.cpu_name
                             });

      html.push('<tr><td colspan="2"><hr /></td></tr>');
      html.push('<tr>');
      html.push('<td>Valgrind</td>');
      html.push('<td>');
      html.push(segmented_search);
      html.push('</td>');
      html.push('</tr>');
      html.push('');
      html.push('<tr>');
      html.push('<td>');
      html.push('Valgrind stack');
      html.push('</td>');
      html.push('<td><pre>' + escape_html(doc.valgrinddata) + '</pre></td>');
      html.push('</tr>');
      html.push('');
      html.push('<tr>');
      html.push('<td>');
      html.push('Date');
      html.push('</td>');
      html.push('<td>');
      html.push(doc.datetime);
      html.push('</td>');
      html.push('</tr>');
      html.push('');
      html.push('<tr>');
      html.push('<td>');
      html.push('Result');
      html.push('</td>');
      html.push('<td>');
      html.push('<a href=\'' + list_path + '/results/crash_result_id/results?include_docs=true&startkey=["' + doc.result_id + '"]&endkey=["' + doc.result_id + ', {}"]\'>' + doc.result_id + '</a>');
      html.push('</td>');
      html.push('</tr>');
      html.push('');
      html.push('<tr>');
      html.push('<td>');
      html.push('url');
      html.push('</td>');
      html.push('<td>');
      html.push('<a href="' + doc.location_id + '">' + escape_html(doc.location_id) + '</a>');
      html.push('</td>');
      html.push('</tr>');
      html.push('');
      html.push('<tr>');
      html.push('<td>&nbsp;</td>');
      html.push('<td>');
      html.push('<a href=\'' + list_path + '/result_locations/crash_location/results?include_docs=true&startkey=["' + escape(doc.location_id) + '"]&endkey=["' + escape(doc.location_id) + ', {}"]\'>Search Results by Location</a>');
      html.push('; ');
      html.push('<a href="https://bugzilla.mozilla.org/buglist.cgi?field0-0-0=bug_file_loc&type0-0-1=substring&field0-0-1=longdesc&classification=Client%20Software&classification=Components&query_format=advanced&value0-0-1=' + escape(doc.location_id) + '&type0-0-0=substring&value0-0-0=' + escape(doc.location_id) + '">Search Bugzilla by Location</a>');
      html.push('</td>');
      html.push('</tr>');
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
