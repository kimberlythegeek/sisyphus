var html = new htmlbuffer(); // buffer of html fragments

function history_summary_html() {

  var row;
  var previous_key = null;
  var counters = { total: 0, os: {}, branch: {}, cpu: {} };
  var firstdate; // first date for a given key value
  var lastdate;  // last date for a given key value
  var filter = {};    // filter results using object properties

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
  html.push('  <title>' + key_options.name + ' History Summary - Bug Hunter</title>');
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
  html.push('<h1>' + key_options.name + ' History Summary</h1>');
  html.push('<div id="content">');
  html.push('<div id="toolbar">');
  html.push('<span id="filter_display"><span id="filter_text"></span> <button type="button" id="modify_filter">Modify Filter</button></span>');
  html.push('</div>');
  html.send('\n');

  function sendhtml() {

    if (previous_key === null)
      return;

    html.push('<tr>');
    html.push('<td width="50%">' + escape_html(previous_key[previous_key.length - 1]) + '</td>');
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

    /*
     * The startkey of the results_by_type view passed to the
     * "details" list function must begin as
     *
     * assertions ["history_assertion", "assertion"]
     * crashes    ["history_crash",     "crash",    "crashsignature"]
     * valgrinds  ["history_valgrind",  "valgrind", "valgrindsignature"]
     *
     * The "details" list function will stop getting rows when it differs
     * in values for the specified startkey.
     */
    html.push('<td>');
    var key_item;
    var escaped_key = [encodeURIComponent(key_item).replace(/\'/g, '&apos;') for each (key_item in previous_key)];
    var history_type;
    var result_type;
    var history_list;
    var result_list;
    switch(key_options.field) {
    case 'assertion':
      history_type = 'history_assertion';
      history_list = 'history_assertions_details';
      result_type  = 'result_assertion';
      result_list  = 'result_assertions_details';
      break;
    case 'crashsignature':
      history_type = 'history_crash';
      history_list = 'history_crashes_details';
      result_type  = 'result_crash';
      result_list  = 'result_crashes_details';
      break;
    case 'valgrindsignature':
      history_type = 'history_valgrind';
      history_list = 'history_valgrinds_details';
      result_type  = 'result_valgrind';
      result_list  = 'result_valgrinds_details';
      break;
    }

    var history_key = [history_type].concat(escaped_key);
    var result_key  = [result_type].concat(escaped_key);

    html.push('<p><a href=\'../' + history_list + '/results_by_type?include_docs=true' +
              '&startkey=' +  history_key.toSource() +
              (req.query.filter ? ('&filter=' + req.query.filter) : '') +
              '\'>history</a></p>');

    html.push('<p><a href=\'../' + result_list + '/results_by_type?include_docs=true' +
              '&startkey=' +  result_key.toSource() +
              (req.query.filter ? ('&filter=' + req.query.filter) : '') +
              '\'>results</a></p>');

    html.push('</td>');

    html.push('</tr>');

    html.send();
  }

  var found_results = false;

  while ((row = getRow())) {

    var doc = row.doc;

    /*
     * We want to stop getting rows as soon as the current row no longer
     * matches the specified startkey.
     *
     * For assertions, the startkey is ["history_assertion", "assertion"] but
     * for crashes it is ["history_crash", "crash", "crashsignature"] and for
     * valgrinds it is ["history_valgrind", "valgrind", "valgrindsignature"]
     */
    var stop = false;
    switch(key_options.field) {
    case "assertion":
      if (startkey[0] != "history_assertion")
        stop = true;
      break;
    case "crashsignature":
      if (startkey[0] != "history_crash")
        stop = true;
      break;
    case "valgrindsignature":
      if (startkey[0] != "history_valgrind")
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
            !(doc.firstdatetime < filter[date_name]))
          keep = false;
        else if (filter[date_type] == 'after' &&
                 (!(doc.firstdatetime > filter[date_name]) &&
                  !(doc.lastdatetime > filter[date_name])))
          keep = false;
        else if (filter[date_type] == 'notbefore' &&
                 (doc.firstdatetime < filter[date_name]))
          keep = false;
        else if (filter[date_type] == 'notafter' &&
                 (doc.lastdatetime > filter[date_name]))
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

    if (!found_results) {
      found_results = true;
      html.push('<table border="1" cellspacing="0" cellpadding="1">');
      html.push('<thead>');
      html.push('<tr>');
      html.push('<th>' + key_options.name + '</th>');
      html.push('<th>Date Range</th><th colspan="4">URL Counts Total/Branches/Operating System/CPU</th>');
      html.push('<th>Details</th>');
      html.push('</tr>');
      html.push('</thead>');
      html.push('<tbody>');
    }

    /*
     * The history views are keyed as:
     * history_assertion ["history_assertion", "assertion", "assertionfile", ...]
     * history_crash     ["history_crash",     "crash",     "crashsignature", ...]
     * history_valgrind  ["history_valgrind",  "valgrind",  "valgrindsignature", ...]
     *
     * For the summary, we want to break assertions only on the value
     * of the assertion field, but want to break the crashes on
     * crashsignature and valgrinds on valgrindsignature.
     *
     * The current_key and previous_key are arrays. The last item of the array is the
     * value to be displayed to the user.
     */
    var current_key;

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

    if (previous_key !== null && current_key + '' != previous_key + '') {
      sendhtml();
      counters = { total: 0, os: {}, branch: {}, cpu: {} };
      firstdate = lastdate = '';
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
      firstdate = doc.firstdatetime;
    else if (doc.firstdatetime < firstdate)
      firstdate = doc.firstdatetime;

    if (!lastdate)
      lastdate = doc.lastdatetime;
    else if (doc.lastdatetime > lastdate)
      lastdate = doc.lastdatetime;

    counters.total += doc.location_id_list.length;
    counters.os[doc.os_name].total += doc.location_id_list.length;
    counters.os[doc.os_name].versions[doc.os_version] += doc.location_id_list.length;
    counters.branch[doc.branch] += doc.location_id_list.length;
    counters.cpu[doc.cpu_name] += doc.location_id_list.length;

    previous_key = current_key.slice(0);
  }

  if (found_results)
    sendhtml();
  else
    send('<h2>Zarro!</h2>');

  html.push('</tbody>');
  html.push('</table>');
  html.push('</div>'); // detail
  html.push('</div>'); // content
  html.push('</body>');
  html.push('</html>');

  html.send();
}
