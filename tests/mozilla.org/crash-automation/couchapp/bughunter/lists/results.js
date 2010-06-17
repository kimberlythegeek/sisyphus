function(head, req) {
  // !json templates.results
  // !code lib/bughunter.js
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code vendor/couchapp/template.js


  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // thier priority. In this case HTML is the preferred format, so it comes first.
  provides("html",
           function() {

             send(template(templates.results.header, {
                           }));


             var row, key;
             var segmented_search;
             var cacheddocs = [];

             while ((row = getRow())) {
               cacheddocs.push(row);
             }

             var cmp_rows = (function (l, r) {
                               // sort by datetime
                               if (l.doc.datetime < r.doc.datetime)
                                 return -1;
                               if (l.doc.datetime > r.doc.datetime)
                                 return +1;

                               // group by result id
                               var lresult_id, rresult_id;
                               if ('result_id' in l.doc)
                                 lresult_id = l.doc.result_id;
                               else
                                 lresult_id = l.doc._id;

                               if ('result_id' in r.doc)
                                 rresult_id = r.doc.result_id;
                               else
                                 rresult_id = r.doc._id;

                               if (lresult_id < rresult_id)
                                 return -1;
                               if (lresult_id > rresult_id)
                                 return +1;

                               // next sort header documents first
                               if (l.doc.type.search('header') != -1)
                                 return -1;
                               if (r.doc.type.search('header') != -1)
                                 return +1;

                               // next sort by document type
                               if (l.doc.type < r.doc.type)
                                 return -1;
                               if (l.doc.type > r.doc.type)
                                 return +1;

                               return 0;
                             });

             cacheddocs.sort(cmp_rows);

             try {

               for (var irow = 0; irow < cacheddocs.length; irow++) {
                 var row = cacheddocs[irow];
                 switch (row.doc.type) {
                 case 'result_header_crashtest':
                   send(template(templates.results.crash_header, {
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
                                   location_id  : row.doc.url,
                                   escaped_location : encodeURI(row.doc.url),
                                   steps     : steps_to_html(row.doc.steps),
                                   exitstatus: row.doc.exitstatus,
                                   reproduced: row.doc.reproduced,
                                   attachments: attachments_to_html(row.doc)
                                 }));
                   break;
                 case 'result_header_unittest':
                   send(template(templates.results.unittest_header, {
                                   result_id : row.doc._id,
                                   test      : row.doc.test,
                                   extra_test_args : row.doc.extra_test_args,
                                   product   : row.doc.product,
                                   branch    : row.doc.branch,
                                   buildtype : row.doc.buildtype,
                                   os_name   : row.doc.os_name,
                                   os_version: row.doc.os_version,
                                   cpu_name  : row.doc.cpu_name,
                                   datetime  : row.doc.datetime,
                                   changeset : row.doc.changeset,
                                   exitstatus : row.doc.exitstatus,
                                   returncode: row.doc.returncode,
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

                   send(template(templates.results.crash_detail, {
                                   segmented_search: segmented_search,
                                   datetime       : row.doc.datetime,
                                   result_id      : row.doc.result_id,
                                   location_id    : row.doc.location_id,
                                   escaped_location : encodeURI(row.doc.location_id),
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

                   send(template(templates.results.assertion_detail, {
                                   segmented_search : segmented_search,
                                   count          : row.doc.count,
                                   datetime       : row.doc.datetime,
                                   result_id      : row.doc.result_id,
                                   location_id    : row.doc.location_id,
                                   escaped_location : encodeURI(row.doc.location_id)
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

                   send(template(templates.results.valgrind_detail, {
                                   segmented_search  : segmented_search,
                                   valgrinddata      : row.doc.valgrinddata,
                                   datetime          : row.doc.datetime,
                                   result_id         : row.doc.result_id,
                                   location_id       : row.doc.location_id,
                                   escaped_location : encodeURI(row.doc.location_id)
                                 }));
                   break;
                 }
               }
             }
             catch(ex) {
               send(ex);
             }

             return template(templates.results.footer, {
                             });
           });
};
