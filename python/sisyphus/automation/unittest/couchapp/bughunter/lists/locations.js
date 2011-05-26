function(head, request) {
  // !json templates.locations
  // !code lib/bughunter.js
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code vendor/couchapp/template.js


  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // thier priority. In this case HTML is the preferred format, so it comes first.
  provides("html",
           function() {

             function attachments_to_html(attachments) {
               var s = '';
               var attachment_list = [];
               for (var filename in attachments) {
                 attachment_list.push(filename);
               }
               attachment_list.sort();
               for (var i = 0; i < attachment_list.length; i++) {
                 filename = attachment_list[i];
                 s += '<li><a href="/unittest/' + row.doc._id + '/' + filename + '">' + filename + '</a></li>';
               }
               if (s) {
                 s = '<ul>' + s + '</ul>';
               }
               return s;
             }

             function steps_to_html(steps) {
               if (!steps)
                 return 'No steps found.';

               var s = '';
               for (var i = 0; i < steps.length; i++) {
                 s += '<li>' + steps[i] + '</li>';
               }
               if (s) {
                 s = '<ol>' + s + '</ol>';
               }
               return s;
             }


             function extra_to_html(extra) {
               if (!extra)
                 return 'No extra data found.';

               var s = '<ul>';
               for (var prop in extra) {
	         s += '<li>' + prop + ' = ' + extra[prop] + '<\/a></li>';
               }
               s += '<\/ul>';
               return s;
             }

             try {

               var row, key;
               var segmented_search;
               var previous_location = '';
               var current_location = '';

               send(template(templates.locations.header, {
                             }));

               while ((row = getRow())) {
                 if (row.doc.location_id && row.doc.location_id != previous_location)
                 {
                   current_location = row.doc.location_id;
                 }
                 if (current_location != previous_location)
                 {
                   previous_location = current_location;
                   send('<h2>Location: ' + current_location + '<\/h2>');
                 }

                 switch (row.doc.type) {
                 case 'result':
                   send(template(templates.locations.result_header, {
                                   result_id : row.doc._id,
                                   test           : row.doc.test,
                                   extra_test_args : row.doc.extra_test_args,
                                   product   : row.doc.product,
                                   branch    : row.doc.branch,
                                   buildtype : row.doc.buildtype,
                                   os_name   : row.doc.os_name,
                                   os_version: row.doc.os_version,
                                   cpu_name  : row.doc.cpu_name,
                                   datetime  : row.doc.datetime,
                                   changeset : row.doc.changeset,
                                   steps     : steps_to_html(row.doc.steps),
                                   exitstatus: row.doc.exitstatus,
                                   attachments: attachments_to_html(row.doc._attachments)
                                 }));
                   break;
                 case 'result_crash':
                   segmented_search =
                     segmented_key_search('history',
                                          '/history/_design/bughunter/_list/crashes/by_type_message',
                                          'crash',
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

                   send(template(templates.locations.crash_detail, {
                                   segmented_search: segmented_search,
                                   test           : row.doc.test,
                                   extra_test_args : row.doc.extra_test_args,
                                   datetime       : row.doc.datetime,
                                   result_id      : row.doc.result_id,
                                   location_id    : row.doc.location_id,
                                   extra          : extra_to_html(row.doc.extra)
                                 }));
                   break;
                 case 'result_assertion':
                   segmented_search =
                     segmented_key_search('history',
                                          '/history/_design/bughunter/_list/assertions/by_type_message',
                                          'assertion',
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

                   send(template(templates.locations.assertion_detail, {
                                   segmented_search : segmented_search,
                                   count          : row.doc.count,
                                   test           : row.doc.test,
                                   extra_test_args : row.doc.extra_test_args,
                                   datetime       : row.doc.datetime,
                                   result_id      : row.doc.result_id,
                                   location_id    : row.doc.location_id
                                 }));
                   break;
                 case 'result_valgrind':
                   segmented_search =
                     segmented_key_search('history',
                                          '/history/_design/bughunter/_list/valgrinds/by_type_message',
                                          'valgrind',
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

                   send(template(templates.locations.valgrind_detail, {
                                   segmented_search  : segmented_search,
                                   test           : row.doc.test,
                                   extra_test_args : row.doc.extra_test_args,
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

             return template(templates.locations.footer, {
                             });
           });
};
