function(head, req) {
  // !json templates.history_crashes
  // !code lib/bughunter.js
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code vendor/couchapp/template.js


  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // thier priority. In this case HTML is the preferred format, so it comes first.
  provides("html", function() {

             function location_id_list_to_links(location_id_list) {
               var s = '<ol>';
               for (var i = 0; i < location_id_list.length; i++) {
                 if (location_id_list[i] != 'head')
	           s += '<li><a href="' + location_id_list[i] + '">' +
                        location_id_list[i] + '<\/a></li>';
               }
               s += '<\/ol>';
               return s;
             }
             send(template(templates.history_crashes.header, {
                           }));
             var row, key;
             while ((row = getRow())) {

               var bug_list = row.doc.bug_list;

               if (!bug_list || ! 'open' in bug_list || ! 'closed' in bug_list) {
                 bug_list = {open : [], closed : []};
               }

               var segmented_search = segmented_key_search('results',
                                                           listPath() + '/result_crashes/results_by_type',
                                                           'result_crash',
                                                           {
                                                             crash        : row.doc.crash,
                                                             crashsignature: row.doc.crashsignature,
                                                             product      : row.doc.product,
                                                             branch       : row.doc.branch,
                                                             buildtype    : row.doc.buildtype,
                                                             os_name      : row.doc.os_name,
                                                             os_version   : row.doc.os_version,
                                                             cpu_name     : row.doc.cpu_name
                                                           });

               send(template(templates.history_crashes.detail, {
                               segmented_search : segmented_search,
                               firstdatetime  : row.doc.firstdatetime,
                               lastdatetime   : row.doc.lastdatetime,
                               open_bugs      : bug_list.open.join(', '),
                               closed_bugs    : bug_list.closed.join(', '),
                               location_id_links: location_id_list_to_links(row.doc.location_id_list)
                             }));
             }
             return template(templates.history_crashes.footer, {
                           });
           });
};
