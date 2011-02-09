function(head, req) {
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code lib/bughunter.js

  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // their priority. In this case HTML is the preferred format, so it comes first.
  provides("html", function() {

    html = new htmlbuffer();
    var app_path = assetPath();

    var startkey = req.query.startkey;
    var endkey   = req.query.endkey;

    html.push('<!DOCTYPE html>');
    html.push('<html>');
    html.push('  <head>');
    html.push('    <title>Result Counts - Bug Hunter</title>');
    html.push('    <link rel="stylesheet" href="' + app_path + '/style/main.css" type="text/css"/>');
    html.push('    <script src="/_utils/script/json2.js" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/sha1.js" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.js?1.4.2" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.couch.js?1.0.0" type="text/javascript"></script>');
    html.push('    <script src="/_utils/script/jquery.dialog.js?1.0.0" type="text/javascript"></script>');
    html.push('    <link href="' + app_path + '/script/jquery-ui/css/jquery-ui-1.8.2.custom.css" rel="stylesheet" type="text/css"/>');
    html.push('    <script src="' + app_path + '/script/jquery-ui/js/jquery-ui-1.8.2.custom.min.js"></script>');
    html.push('    <script src="' + app_path + '/script/application.js" type="text/javascript"></script>');
    html.push('    <script type="text/javascript">');
    html.push('      // tell date_filter.js whether the key is a simple date or');
    html.push('      // if it is an array with a date as the first element.');
    html.push('      var key_type = Array;');
    html.push('    </script>');
    html.push('    <script src="' + app_path + '/script/date-filter.js" type="text/javascript"></script>');
    html.push('  </head>');
    html.push('  <body>');
    html.push('    <div id="wrap">');
    html.push('');
    html.push('      <h1>Result Counts</h1>');
    html.push('');
    html.send();
    html.push('      <div id="content">');
    html.push('        <div id="toolbar">');
    html.push('          <span id="filter_display"><span id="filter_text"></span> <button type="button" id="modify_filter">Modify Filter</button></span>');
    html.push('        </div>');
    html.push('');
    html.push('        <table>');
    html.push('          <tr>');
    html.push('            <th>Result Type</th>');
    html.push('            <th>Count</th>');
    html.push('          </tr>');

    var row;
    var counts_hash = {};
    var worker_id;
    var doc_type;
    var signature_id;
    var job_hash = {};
    var re_result_header = new RegExp('result_header_');

    while ((row = getRow())) {
      var doc = row.doc;
      if (!doc)
        continue;

      worker_id = doc.worker_id;
      doc_type  = doc.type;
      if (! (worker_id in counts_hash))
        counts_hash[worker_id] = {job_hash: {}, jobs: 0};

      if (! (doc_type in counts_hash[worker_id]))
        counts_hash[worker_id][doc_type] = 0;

      ++counts_hash[worker_id][doc_type];

      if (re_result_header.exec(doc_type))
      {
        signature_id = doc._id.replace(/_result_.*/, '');
        counts_hash[worker_id].job_hash[signature_id] = 1;
      }

    }

    var jobs = 0;
    var workers = [];
    var crash_test_runs = 0;
    var unit_test_runs  = 0;
    var crashes         = 0;
    var assertions      = 0;
    var valgrinds       = 0;
    var worker_counts;

    for (worker_id in counts_hash)
    {
      workers.push(worker_id);
      worker_counts = counts_hash[worker_id];
      if (worker_counts['result_header_crashtest'])
        crash_test_runs += worker_counts['result_header_crashtest'];
      if (worker_counts['result_header_unittest'])
        unit_test_runs  += worker_counts['result_header_unittest'];
      if (worker_counts['result_crash'])
        crashes         += worker_counts['result_crash'];
      if (worker_counts['result_assertion'])
        assertions      += worker_counts['result_assertion'];
      if (worker_counts['result_valgrind'])
        valgrinds       += worker_counts['result_valgrind'];

      for (signature_id in worker_counts.job_hash) {
        ++jobs;
        ++worker_counts.jobs;
      }

    }
    workers.sort();

    html.push('<tr>');
    html.push('<td>total jobs</td>');
    html.push('<td align="right">');
    html.push(jobs);
    html.push('</td>');
    html.push('</tr>');

    html.push('<tr>');
    html.push('<td>total crash test runs</td>');
    html.push('<td align="right">');
    html.push(crash_test_runs);
    html.push('</td>');
    html.push('</tr>');

    html.push('<tr>');
    html.push('<td>total unit test runs</td>');
    html.push('<td align="right">');
    html.push(unit_test_runs);
    html.push('</td>');
    html.push('</tr>');

    html.push('<tr>');
    html.push('<td>total crashes</td>');
    html.push('<td align="right">');
    html.push(crashes);
    html.push('</td>');
    html.push('</tr>');

    html.push('<tr>');
    html.push('<td>total assertions</td>');
    html.push('<td align="right">');
    html.push(assertions);
    html.push('</td>');
    html.push('</tr>');

    html.push('<tr>');
    html.push('<td>total valgrinds</td>');
    html.push('<td align="right">');
    html.push(valgrinds);
    html.push('</td>');
    html.push('</tr>');

    for (var i = 0; i < workers.length; i++) {
      worker_id       = workers[i];
      worker_counts   = counts_hash[worker_id];
      jobs            = worker_counts.jobs;
      crash_test_runs = worker_counts['result_header_crashtest'];
      unit_test_runs  = worker_counts['result_header_unittest'];
      crashes         = worker_counts['result_crash'];
      assertions      = worker_counts['result_assertion'];
      valgrinds       = worker_counts['result_valgrind'];

      html.push('<tr>');
      html.push('<td>' + worker_id + ' jobs</td>');
      html.push('<td align="right">');
      html.push(jobs);
      html.push('</td>');
      html.push('</tr>');

      html.push('<tr>');
      html.push('<td>' + worker_id + ' crash test runs</td>');
      html.push('<td align="right">');
      html.push(crash_test_runs);
      html.push('</td>');
      html.push('</tr>');

      html.push('<tr>');
      html.push('<td>' + worker_id + ' unit test runs</td>');
      html.push('<td align="right">');
      html.push(unit_test_runs);
      html.push('</td>');
      html.push('</tr>');

      html.push('<tr>');
      html.push('<td>' + worker_id + ' crashes</td>');
      html.push('<td align="right">');
      html.push(crashes);
      html.push('</td>');
      html.push('</tr>');

      html.push('<tr>');
      html.push('<td>' + worker_id + ' assertions</td>');
      html.push('<td align="right">');
      html.push(assertions);
      html.push('</td>');
      html.push('</tr>');

      html.push('<tr>');
      html.push('<td>' + worker_id + ' valgrinds</td>');
      html.push('<td align="right">');
      html.push(valgrinds);
      html.push('</td>');
      html.push('</tr>');
    }

    html.push('</table>');
    html.push('');
    html.push('</div> <!-- content -->');
    html.push('</div> <!-- wrap -->');
    html.push('</body>');
    html.push('</html>');
    html.send();
  });
};
