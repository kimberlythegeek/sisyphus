function(head, request) {
  // !json templates.assertions
  // !code lib/bughunter.js
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code vendor/couchapp/template.js


  // The provides function serves the format the client requests.
  // The first matching format is sent, so reordering functions changes
  // thier priority. In this case HTML is the preferred format, so it comes first.
  provides("html", function() {

             send(template(templates.assertions.header, {
                           }));

             var row;
             var endkey;
             var limit = 1000;

             if (request.query.limit)
               limit = request.query.limit;

             while ((row = getRow())) {

               var segmented_search =
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

               send(template(templates.assertions.detail, {
                               segmented_search : segmented_search,
                               count          : row.doc.count,
                               test           : row.doc.test,
                               extra_test_args : row.doc.extra_test_args,
                               datetime       : row.doc.datetime,
                               result_id      : row.doc.result_id,
                               location_id    : row.doc.location_id,
                               escaped_location : escape(row.doc.location_id)
                             }));
             }

             return template(templates.assertions.footer, {
                           });
             return '';
           });
};
