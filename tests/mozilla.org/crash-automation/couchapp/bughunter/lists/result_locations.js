function(head, req) {
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code lib/bughunter.js

  var key_options = {name:  'Assertion', field: 'assertion'};

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
    html.push('    <title>Crash Test Results by Location - Bug Hunter</title>');
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
    html.push('    <div id="wrap">');
    html.push('');
    html.push('      <h1>Results by Location</h1>');
    html.push('      <div id="content">');
    html.push('        <div id="toolbar">');
    html.push('          <span id="filter_display"><span id="filter_text"></span> <button type="button" id="modify_filter">Modify Filter</button></span>');
    html.push('        </div>');
    html.send();

    try {

      var row, key;
      var segmented_search;
      var previous_location = '';
      var current_location = '';
      var stop = false;

      html.push('<table>');

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

        if (doc.location_id && doc.location_id != previous_location)
        {
          current_location = doc.location_id;
        }
        else if (doc.url && doc.url != previous_location)
        {
          current_location = doc.url;
        }
        if (current_location != previous_location)
        {
          previous_location = current_location;
          send('<h2>Location: ' + escape_html(current_location) + '<\/h2>');
        }


        switch (doc.type) {
        case 'result_header_crashtest':
          html.push('<tr><td colspan="2"><hr style="border-style: double;"/></td></tr>');
          html.push('<tr>');
          html.push('<td>');
          html.push('Result id:');
          html.push('</td>');
          html.push('<td>');
          html.push('<a href=\'' + list_path + '/results/crash_result_id/results?include_docs=true&startkey=["' + doc._id + '"]&endkey=["' + doc._id + ', {}"]\'>' + doc._id + '</a>');
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Socorro Signature:');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.signature);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Product');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.product);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Branch');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.branch);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Build type');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.buildtype);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Operating System');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.os_name + ' ' + doc.os_version);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Processor');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.cpu_name);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Datetime');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.datetime);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Changeset');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.changeset);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Location');
          html.push('</td>');
          html.push('<td>');
          html.push('<a href="' + doc.url + '">' + escape_html(doc.url) + '</a>');
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Steps');
          html.push('</td>');
          html.push('<td>');
          html.push(steps_to_html(doc.steps));
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Exit Status');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.exitstatus);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Reproduced');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.reproduced);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Attachments');
          html.push('</td>');
          html.push('<td>');
          html.push(attachments_to_html(doc._id, doc._attachments));
          html.push('</td>');
          html.push('</tr>');
          html.send();
          break;

        case 'result_crash':
          segmented_search =
            segmented_key_search('history',
                                 listPath() + '/history_crashes_summary/crash_type/results',
                                 'history_crash',
                                 {
                                   crash        : doc.crash,
                                   crashsignature: doc.crashsignature,
                                   product      : doc.product,
                                   branch       : doc.branch,
                                   buildtype    : doc.buildtype,
                                   os_name      : doc.os_name,
                                   os_version   : doc.os_version,
                                   cpu_name     : doc.cpu_name
                                 });

          html.push('<tr>');
          html.push('<td>Crash</td>');
          html.push('<td>');
          html.push(segmented_search);
          html.push('</td>');
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
          html.push('Location');
          html.push('</td>');
          html.push('<td>');
          html.push('<a href="' + doc.location_id + '">' + escape_html(doc.location_id) + '</a>');
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('extra');
          html.push('</td>');
          html.push('<td>');
          html.push(extra_to_html(doc.extra));
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Attachments');
          html.push('</td>');
          html.push('<td>');
          html.push(attachments_to_html(doc._id, doc._attachments));
          html.push('</td>');
          html.push('</tr>');
          html.send();
          break;

        case 'result_assertion':
          segmented_search =
            segmented_key_search('history',
                                 listPath() + '/history_assertions_summary/crash_type/results',
                                 'history_assertion',
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

          html.push('<tr>');
          html.push('<td>Assertion</td>');
          html.push('<td>');
          html.push(segmented_search);
          html.push('</td>');
          html.push('</tr>');
          html.push('');
          html.push('<tr>');
          html.push('<td>');
          html.push('Count');
          html.push('</td>');
          html.push('<td>');
          html.push(doc.count);
          html.push('</td>');
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
          html.push('Location');
          html.push('</td>');
          html.push('<td>');
          html.push('<a href="' + doc.location_id + '">' + escape_html(doc.location_id) + '</a>');
          html.push('</td>');
          html.push('</tr>');
          html.send();
          break;

        case 'result_valgrind':
          segmented_search =
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
          html.push('Location');
          html.push('</td>');
          html.push('<td>');
          html.push('<a href="' + doc.location_id + '">' + escape_html(doc.location_id) + '</a>');
          html.push('</td>');
          html.push('</tr>');
          html.send();
          break;
        }
      }
    }
    catch(ex) {
      send(ex);
    }

    html.push('</table>');
    html.push('</div> <!-- content -->');
    html.push('</div> <!-- wrap -->');
    html.push('</body>');
    html.push('</html>');
    html.send();

  });
};
