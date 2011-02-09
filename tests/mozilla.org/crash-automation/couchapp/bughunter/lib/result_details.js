var html = new htmlbuffer(); // buffer of html fragments

function result_details_html() {

  var row;
  var previous_key = null;
  var previous_product_key = null;
  var counters = { total: 0, os: {}, branch: {}, cpu: {} };
  var firstdate; // first date for a given key value
  var lastdate;  // last date for a given key value
  var filter = {};    // filter results using object properties
  var details = []; // array of objects containing the history details.

  if (req.query.filter) {
    try {
      filter = JSON.parse(req.query.filter);
    }
    catch (ex) {
      send('Error parsing filter: ' + ex);
    }
  }

  var startkey = req.query.startkey;

  html.push('<!DOCTYPE html>');
  html.push('<html>');
  html.push('  <head>');
  html.push('  <title>' + key_options.name + ' Result Details - Bug Hunter</title>');
  html.push('    <link rel="stylesheet" href="../../style/main.css" type="text/css"/>');
  html.push('    <script src="/_utils/script/json2.js" type="text/javascript"></script>');
  html.push('    <script src="/_utils/script/sha1.js" type="text/javascript"></script>');
  html.push('    <script src="/_utils/script/jquery.js?1.4.2" type="text/javascript"></script>');
  html.push('    <script src="/_utils/script/jquery.couch.js?1.0.0" type="text/javascript"></script>');
  html.push('    <script src="/_utils/script/jquery.dialog.js?1.0.0" type="text/javascript"></script>');

  html.push('    <link href="../../script/jquery-ui/css/jquery-ui-1.8.2.custom.css" rel="stylesheet" type="text/css"/>');
  html.push('    <script src="../../script/jquery-ui/js/jquery-ui-1.8.2.custom.min.js"></script>');

  html.push('    <script src="../../script/application.js" type="text/javascript"></script>');
  // Must define key_options before including script/date-field-branch-os-filter.js
  html.push('    <script type="text/javascript">');
  html.push('      var key_options = ' + JSON.stringify(key_options) + ';');
  html.push('    </script>');
  html.push('    <script src="../../script/date-field-branch-os-filter.js" type="text/javascript"></script>');
  html.push('  </head>');
  html.push('  <body>');
  html.push('  <div id="wrap">');
  html.push('<h1>' + key_options.name + ' Result Details</h1>');
  html.push('<div id="content">');
  html.push('<div id="toolbar">');
  html.push('<span id="filter_display"><span id="filter_text"></span> <button type="button" id="modify_filter">Modify Filter</button></span>');
  html.push('</div>');
  html.send('\n');

  function sendhtml() {

    if (previous_key === null)
      return;

    html.push('<h2>' + escape_html(previous_key[previous_key.length - 1]) + '</h2>');

    html.push('<table border="1" cellspacing="0" cellpadding="1" width="100%">');
    html.push('<thead>');
    html.push('<tr>');
    html.push('<th>Date Range</th><th colspan="4">Instance Counts Total/Branches/Operating System/CPU</th>');
    html.push('<th>Details</th>');
    html.push('</tr>');
    html.push('</thead>');
    html.push('<tbody>');

    html.push('<tr>');
    html.push('<td>' + firstdate + ' - ' + lastdate + '</td>');
    html.push('<td>' + counters.total + '</td>');

    // branch:99, ...
    htmlpieces = [];
    htmlpieces.push('<ul>');

    var branchlist = [];
    for (branch in counters.branch)
      branchlist.push(branch);

    branchlist.sort();

    for each (branch in branchlist)
      htmlpieces.push('<li>' + branch + ' (' + counters.branch[branch] + ')</li>');

    htmlpieces.push('</ul>');
    html.push('<td>');
    html.push(htmlpieces.join(''));
    html.push('</td>');

    // os:99 (ver1:99, ver2:99,...), ...
    var htmlpieces = [];
    var oslist = [];

    for (var os in counters.os)
      oslist.push(os);

    oslist.sort();

    htmlpieces.push('<ul>');

    for each (os in oslist) {
      htmlpieces.push('<li>' + os + ' (' + counters.os[os].total + ')');
      var htmlsubpieces = [];
      htmlsubpieces.push('<ul>');

      var osverlist = [];

      for (osver in counters.os[os].versions)
        osverlist.push(osver);

      osverlist.sort();

      for each (osver in osverlist)
        htmlsubpieces.push('<li>' + osver + ' (' + counters.os[os].versions[osver] + ')</li>');

      htmlsubpieces.push('</ul></li>');
      htmlpieces[htmlpieces.length-1] += htmlsubpieces.join('');
    }

    htmlpieces.push('</ul>');
    html.push('<td>');
    html.push(htmlpieces.join(''));
    html.push('</td>');

    // cpu:99, ...
    htmlpieces = [];
    htmlpieces.push('<ul>');

    var cpulist = [];

    for (cpu in counters.cpu)
      cpulist.push(cpu);

    cpulist.sort();

    for each (cpu in cpulist)
      htmlpieces.push('<li>' + cpu + ' (' + counters.cpu[cpu] + ')</li>');

    htmlpieces.push('</ul>');
    html.push('<td>');
    html.push(htmlpieces.join(''));
    html.push('</td>');

    html.push('<td>');
    html.push('<p><a href="#">retest</a></p>');
    html.push('</td>');

    html.push('</tr>');
    html.push('</tbody>');
    html.push('</table>');

    var detail;

    for each (detail in details) {
      html.push('<div>');
      // product
      var cellwidth = (key_options.field == 'assertion') ? '"20%"' : '"25%"';

      html.push('<table border="1" cellspacing="0" cellpadding="0" width="100%" style="font-weight: bold; margin-top: 1em;">');
      html.push('<tbody>');
      html.push('<tr>');
      html.push('<td width=' + cellwidth + '>' + detail.product + '</td>');
      html.push('<td width=' + cellwidth + '>' + detail.branch + '</td>');
      html.push('<td width=' + cellwidth + '>' + detail.buildtype + '</td>');

      if (key_options.field == 'assertion')
        htmlpieces.push('<td width=' + cellwidth + '>' + detail.assertionfile + '</td>');

      html.push('<td width=' + cellwidth + '>' + detail.firstdate + ' - ' + detail.lastdate + '</td>');
      html.push('</tr>');
      html.push('</tbody>');
      html.push('</table>');
      // os
      var previous_os_key = '';
      html.push('<div style="margin-left: 5em">');
      for each (osdetail in detail.oslist) {
        var current_os_key = osdetail.os_name + osdetail.os_version + osdetail.cpu_name;

        if (previous_os_key && current_os_key != previous_os_key) {
          html.push('</td>');
          html.push('</tr>');
          html.push('</tbody>');
          html.push('</table>');
        }

        if (current_os_key != previous_os_key) {
          html.push('<table border="1" cellspacing="0" cellpadding="0" width="100%" style="margin-top: 1em;">');
          html.push('<tbody>');
          html.push('<tr style="font-weight: bold;">');
          html.push('<td width="33%">' + osdetail.os_name + '</td>');
          html.push('<td width="33%">' + osdetail.os_version + '</td>');
          html.push('<td width="33%">' + osdetail.cpu_name + '</td>');
          html.push('</tr>');
          html.push('<tr>');
          html.push('<td colspan="4">');
        }

        html.push('<table width="100%">');
        html.push('<tr><td colspan="2"><hr /></td></tr>');
        html.push('<tr>');
        html.push('<td>Result</td>');
        html.push('<td>');
        html.push('<a href=\'../results/results_by_result_id?include_docs=true' +
                  '&startkey=["' + osdetail.result_id + '"]' +
                  '&endkey=["' + osdetail.result_id + '", {}]\'>' + osdetail.result_id + '</a>');
        html.push('</td>');
        html.push('</tr>');
        html.push('<tr>');
        html.push('<td>Date</td>');
        html.push('<td>' + osdetail.datetime + '</td>');
        html.push('</tr>');

        switch(key_options.field) {
        case 'assertion':
          html.push('<tr>');
          html.push('<td style="width: 16em;">Count</td>');
          html.push('<td>');
          html.push(osdetail.count);
          html.push('</td>');
          html.push('</tr>');
          break;
        case 'crashsignature':
          html.push('<tr>');
          html.push('<td style="width: 16em;">Extra</td>');
          html.push('<td>');
          html.push(extra_to_html(osdetail.extra));
          html.push('</td>');
          html.push('</tr>');
          if (osdetail.stack) {
            html.push('<tr>');
            html.push('<td style="width: 16em;">Stack</td>');
            html.push('<td>');
            html.push('<pre>' + escape_html(osdetail.stack.join('\n')) + '</pre>');
            html.push('</td>');
            html.push('</tr>');
          }
          html.push('<tr>');
          html.push('<td style="width: 16em;">Attachments</td>');
          html.push('<td>');
          html.push(attachments_to_html(osdetail.docid, osdetail.attachments));
          html.push('</td>');
          html.push('</tr>');
          break;
        case 'valgrindsignature':
          html.push('<tr>');
          html.push('<td style="width: 16em;">Valgrind Stack</td>');
          html.push('<td>');
          html.push('<pre>' + escape_html(osdetail.valgrinddata) + '</pre>');
          html.push('</td>');
          html.push('</tr>');
          break;
        }
        html.push('<tr>');
        html.push('<td style="width: 16em;">url</td>');
        html.push('<td>');
        html.push('<a href="' + osdetail.url + '">' + escape_html(osdetail.url) + '</a>');
        html.push('</td>');
        html.push('</tr>');
        html.push('<tr>');
        html.push('<td>&nbsp;</td>');
        html.push('<td>');
        html.push('<a href=\'../../_list/result_locations/results_by_location?include_docs=true&startkey=["' + escape(osdetail.url) + '"]&endkey=["' + escape(osdetail.url) + '", {}]\'>Search Results by Location</a>');
        html.push('; ');
        html.push('<a href="https://bugzilla.mozilla.org/buglist.cgi?field0-0-0=bug_file_loc&type0-0-1=substring&field0-0-1=longdesc&classification=Client%20Software&classification=Components&query_format=advanced&value0-0-1=' + escape(osdetail.url) + '&type0-0-0=substring&value0-0-0=' + escape(osdetail.url) + '">Search Bugzilla by Location</a>');
        html.push('</td>');
        html.push('</tr>');
        html.push('</table>');
        previous_os_key = current_os_key;
      }
      html.push('</td>');
      html.push('</tr>');
      html.push('</tbody>');
      html.push('</table>');
      html.push('</div>');
    }

    html.send();
  }

  var found_results = false;
  var detail;

  while ((row = getRow())) {

    var doc = row.doc;

    /*
     * We want to stop getting rows as soon as the current row no longer
     * matches the specified startkey.
     *
     * For assertions, the startkey is ["result_assertion", "assertion"] but
     * for crashes it is ["result_crash", "crash", "crashsignature"] and for
     * valgrinds it is ["result_valgrind", "valgrind", "valgrindsignature"]
     */
    var stop = false;
    switch(key_options.field) {
    case "assertion":
      if (startkey[0] != "result_assertion" || startkey[1] != doc["assertion"])
        stop = true;
      break;
    case "crashsignature":
      if (startkey[0] != "result_crash" || startkey[1] != doc["crash"] || startkey[2] != doc["crashsignature"])
        stop = true;
      break;
    case "valgrindsignature":
      if (startkey[0] != "result_valgrind" || startkey[1] != doc["valgrind"] || startkey[2] != doc["valgrindsignature"])
        stop = true;
      break;
    }

    if (stop)
      break;

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
                 doc.datetime < filter[date_name])
          keep = false;
        else if (filter[date_type] == 'notafter' &&
                 doc.datetime > filter[date_name])
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

    found_results = true;

    /*
     * The result views are keyed as:
     * result_assertion ["result_assertion", "assertion", "assertionfile", ...]
     * result_crash     ["result_crash",     "crash",     "crashsignature", ...]
     * result_valgrind  ["result_valgrind",  "valgrind",  "valgrindsignature", ...]
     *
     * For the details, we want to break assertions on the value of
     * the assertion and the assertionfile fields, and want to break
     * the crashes on crashsignature and valgrinds on
     * valgrindsignature.
     *
     * The current_key and previous_key are arrays. The last item of the array is the
     * value to be displayed to the user.
     */
    var current_key;
    var current_product_key = [doc.product, doc.branch, doc.buildtype];

    switch(key_options.field) {
    case 'assertion':
      current_key = [doc['assertion']];
      break;
    case 'valgrindsignature':
      current_key = [doc['valgrind'], doc['valgrindsignature']];
      break;
    case 'crashsignature':
      current_key = [doc['crash'], doc['crashsignature']];
      break;
    }

    if (previous_key && previous_product_key &&
        (current_key + '' == previous_key + '' &&
         current_product_key + '' == previous_product_key + '')) {

      if (doc.datetime < detail.firstdate)
        detail.firstdate = doc.datetime;

      if (doc.datetime > detail.lastdate)
        detail.lastdate = doc.datetime;

    }

    if (previous_key !== null && current_key + '' != previous_key + '') {
      sendhtml();
      counters = { total: 0, os: {}, branch: {}, cpu: {} };
      firstdate = lastdate = '';
    }

    if (current_key + '' != previous_key + '' ||
        current_product_key + '' != previous_product_key + '') {

      detail = {
        product   : doc.product,
        branch    : doc.branch,
        buildtype : doc.buildtype,
        firstdate : doc.datetime,
        lastdate  : doc.datetime,
        oslist    : []
      };

      if (key_options.field == 'assertion')
        detail.assertionfile = doc.assertionfile;

      details.push(detail);
    }

    if (! (doc.os_name in counters.os) )
      counters.os[doc.os_name] = {total: 0, versions: {}};

    if (! (doc.os_version in counters.os[doc.os_name].versions) )
      counters.os[doc.os_name].versions[doc.os_version] = 0;

    if (! (doc.branch in counters.branch) )
      counters.branch[doc.branch] = 0;

    if (! (doc.cpu_name in counters.cpu) )
      counters.cpu[doc.cpu_name] = 0;

    if (!firstdate)
      firstdate = doc.datetime;
    else if (doc.datetime < firstdate)
      firstdate = doc.datetime;

    if (!lastdate)
      lastdate = doc.datetime;
    else if (doc.datetime > lastdate)
      lastdate = doc.datetime;

    var osdetail = {
      docid         : doc._id,
      result_id     : doc.result_id,
      os_name       : doc.os_name,
      os_version    : doc.os_version,
      cpu_name      : doc.cpu_name,
      datetime      : doc.datetime,
      url           : doc.location_id
    };

    var count = 1;
    switch(key_options.field) {
    case 'assertion':
      osdetail.count = doc.count;
      count = doc.count;
      break;
    case 'crashsignature':
      osdetail.extra = doc.extra;
      osdetail.stack = doc.stack;
      osdetail.attachments = doc._attachments;
      break;
    case 'valgrindsignature':
      osdetail.valgrinddata = doc.valgrinddata;
      break;
    }

    counters.total += count;
    counters.os[doc.os_name].total += count;
    counters.os[doc.os_name].versions[doc.os_version] += count;
    counters.branch[doc.branch] += count;
    counters.cpu[doc.cpu_name] += count;

    detail.oslist.push(osdetail);

    previous_key = current_key.slice(0);
    previous_product_key = current_product_key.slice(0);
  }

  if (found_results)
    sendhtml();
  else
    send('<h2>Zarro!</h2>');

  html.push('</div>'); // detail
  html.push('</div>'); // content
  html.push('</body>');
  html.push('</html>');

  html.send();
}
