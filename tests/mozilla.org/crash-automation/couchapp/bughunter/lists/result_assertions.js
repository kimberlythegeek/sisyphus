function(head, req) {
  // !code lib/bughunter.js
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js

  var key_options = {name:  'Assertion', field: 'assertion'};

  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // their priority. In this case HTML is the preferred format, so it comes first.
  provides("html", function() {

    /*
     * temporarily hard code a page limit of 100 documents. this should be exposed
     * in the UI.
     */
    var page_row_limit = 100;
    var page_row_count = 0;

    html = new htmlbuffer();

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
    html.push('  <title>Assertion Results - Bug Hunter</title>');
    html.push('    <link rel="stylesheet" href="../../style/main.css" type="text/css"/>');
    html.push('    <script src="/_utils/script/json2.js" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/sha1.js" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.js?1.4.2" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.couch.js?1.0.0" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.dialog.js?1.0.0" type="text/javascript"></script>');
    html.push('    <script src="../../script/application.js" type="text/javascript"></script>');

    html.push('    <link href="../../script/jquery-ui/css/jquery-ui-1.8.2.custom.css" rel="stylesheet" type="text/css"/>');
    html.push('    <script src="../../script/jquery-ui/js/jquery-ui-1.8.2.custom.min.js" type="text/javascript"></script>');

    // Must define key_options before including script/date-field-branch-os-filter.js
    html.push('    <script type="text/javascript">');
    html.push('      var key_options = ' + JSON.stringify(key_options) + ';');
    html.push('    </script>');
    html.push('    <script src="../../script/date-field-branch-os-filter.js" type="text/javascript"></script>');
    html.push('  </head>');
    html.push('  <body>');
    html.push('');
    html.push('  <div id="wrap">');
    html.push('');
    html.push('  <h1>Assertion Results</h1>');
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
                             listPath() + '/history_assertions_summary/results_by_type',
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

      html.push('<tr><td colspan="2"><hr /></td></tr>');
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
      html.push('<a href=\'../../_list/results/results_by_result_id?include_docs=true&startkey=["' + doc.result_id + '"]&endkey=["' + doc.result_id + ', {}"]\'>' + doc.result_id + '</a>');
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
      html.push('<td>&nbsp;</td>');
      html.push('<td>');
      html.push('<a href=\'../../_list/result_locations/results_by_location?include_docs=true&startkey=["'  + escape(doc.location_id) + '"]&endkey=["' + escape(doc.location_id) + '{},"]\'>Search by Location</a>');
      html.push('</td>');
      html.push('</tr>');
      html.send();

      if (++page_row_count > page_row_limit)
        break;
    }
    html.push('</table>');

    if (row && page_row_count > page_row_limit) {

      req.query.startkey = row.key;
      req.query.startkey_docid = doc._id;

      var nextpagequery = '';
      for (var queryprop in req.query) {
        var queryval = req.query[queryprop];
        switch(typeof(queryval)) {
        case 'object':
          nextpagequery += '&' + queryprop + '=' + escape(queryval.toSource());
          break;
        default:
          if (/true|false/.exec(queryval))
            nextpagequery += '&' + queryprop + '=' + escape(queryval);
          else
            nextpagequery += '&' + queryprop + '="' + escape(queryval) + '"';
          break;
        }
      }
      nextpagequery = nextpagequery.slice(1);

      html.push('<script>');
      html.push('function gotonextpage() { document.location.search = \'' + nextpagequery + '\'; return false; }');
      html.push('</script>');
      html.push('<table width="100%">');
      html.push('<tr>');
      html.push('<td align="left">');
      html.push('<a href="javascript:history.back();void(0)">Previous</a>');
      html.push('</td>');
      html.push('<td align="right">');
      html.push('<a href="javascript:gotonextpage();void(0)">Next</a>');
      html.push('</td>');
      html.push('</tr>');
      html.push('</table>');
    }

    html.push('</div> <!-- content -->');
    html.push('</div> <!-- wrap -->');
    html.push('</body>');
    html.push('</html>');
    html.send();
  });
};
