function(head, req) {
  // !json templates.result_locations
  // !code lib/bughunter.js
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code vendor/couchapp/template.js


  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // thier priority. In this case HTML is the preferred format, so it comes first.
  provides("html",
           function() {

             try {

               var row, key;
               var segmented_search;
               var previous_location = '';
               var current_location = '';

               send(template(templates.result_locations.header, {
                             }));

               while ((row = getRow())) {
                 if (row.doc.location_id && row.doc.location_id != previous_location)
                 {
                   current_location = row.doc.location_id;
                 }
                 else if (row.doc.url && row.doc.url != previous_location)
                 {
                   current_location = row.doc.url;
                 }
                 if (current_location != previous_location)
                 {
                   previous_location = current_location;
                   send('<h2>Location: ' + current_location + '<\/h2>');
                 }

                 switch (row.doc.type) {
                 case 'result':
                   send(template(templates.result_locations.result_header, {
                                   result_id : row.doc._id,
                                   signature : row.doc.signature,
                                   product   : row.doc.product,
                                   branch    : row.doc.branch,
                                   buildtype : row.doc.buildtype,
                                   os_name   : row.doc.os_name,
                                   os_version: row.doc.os_version,
                                   cpu_name  : row.doc.cpu_name,
                                   datetime  : row.doc.datetime,
                                   changeset : row.doc.changeset,
                                   url       : row.doc.url,
                                   steps     : steps_to_html(row.doc.steps),
                                   exitstatus: row.doc.exitstatus,
                                   reproduced: row.doc.reproduced,
                                   attachments: attachments_to_html(row.doc)
                                 }));
                   break;
                 case 'result_crash':
                   segmented_search =
                     segmented_key_search('history',
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

                   send(template(templates.result_locations.crash_detail, {
                                   segmented_search: segmented_search,
                                   datetime       : row.doc.datetime,
                                   result_id      : row.doc.result_id,
                                   location_id    : row.doc.location_id,
                                   extra          : extra_to_html(row.doc.extra),
                                   attachments: attachments_to_html(row.doc)
                                 }));
                   break;
                 case 'result_assertion':
                   segmented_search =
                     segmented_key_search('history',
                                          listPath() + '/history_assertions/results_by_type',
                                          'history_assertion',
                                          {
                                            assertion    : row.doc.assertion,
                                            assertionfile: row.doc.assertionfile,
                                            product      : row.doc.product,
                                            branch       : row.doc.branch,
                                            buildtype    : row.doc.buildtype,
                                            os_name      : row.doc.os_name,
                                            os_version   : row.doc.os_version,
                                            cpu_name     : row.doc.cpu_name
                                          });

                   send(template(templates.result_locations.assertion_detail, {
                                   segmented_search : segmented_search,
                                   count          : row.doc.count,
                                   datetime       : row.doc.datetime,
                                   result_id      : row.doc.result_id,
                                   location_id    : row.doc.location_id
                                 }));
                   break;
                 case 'result_valgrind':
                   segmented_search =
                     segmented_key_search('history',
                                          listPath() + '/history_valgrinds/results_by_type',
                                          'history_valgrind',
                                          {
                                            valgrind    : row.doc.valgrind,
                                            valgrindsignature: row.doc.valgrindsignature,
                                            product      : row.doc.product,
                                            branch       : row.doc.branch,
                                            buildtype    : row.doc.buildtype,
                                            os_name      : row.doc.os_name,
                                            os_version   : row.doc.os_version,
                                            cpu_name     : row.doc.cpu_name
                                          });

                   send(template(templates.result_locations.valgrind_detail, {
                                   segmented_search  : segmented_search,
                                   valgrinddata : row.doc.valgrinddata,
                                   datetime          : row.doc.datetime,
                                   result_id         : row.doc.result_id,
                                   location_id       : row.doc.location_id
                                 }));
                   break;
                 }
               }
             }
             catch(ex) {
               send(ex);
             }

             return template(templates.result_locations.footer, {
                             });
           });
};
