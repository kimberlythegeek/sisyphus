function(head, req) {
  // !json templates.result_crashes
  // !code lib/bughunter.js
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code vendor/couchapp/template.js


  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // thier priority. In this case HTML is the preferred format, so it comes first.
  provides("html", function() {

             send(template(templates.result_crashes.header, {
                           }));
             var row, key;
             while ((row = getRow())) {
               var segmented_search = segmented_key_search('history',
                                                           listPath() + '/history_crashes/results_by_type',
                                                           'history_crash',
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

               send(template(templates.result_crashes.detail, {
                               segmented_search : segmented_search,
                               datetime       : row.doc.datetime,
                               result_id      : row.doc.result_id,
                               location_id    : row.doc.location_id,
                               escaped_location : escape(row.doc.location_id),
                               extra          : extra_to_html(row.doc.extra),
                               attachments: attachments_to_html(row.doc)

                             }));
             }
             return template(templates.result_crashes.footer, {
                           });
             return '';
           });
};
