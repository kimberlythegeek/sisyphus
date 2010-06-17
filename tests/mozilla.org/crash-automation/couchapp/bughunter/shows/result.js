function (doc, req) {
  // !json templates.crashtest_result
  // !json templates.unittest_result
  // !code lib/bughunter.js
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code vendor/couchapp/template.js

  if (doc.type == 'result_header_crashtest')
    return template(templates.crashtest_result, {
                      result_id : doc._id,
                      signature : doc.signature,
                      product   : doc.product,
                      branch    : doc.branch,
                      buildtype : doc.buildtype,
                      os_name   : doc.os_name,
                      os_version: doc.os_version,
                      cpu_name  : doc.cpu_name,
                      datetime  : doc.datetime,
                      changeset : doc.changeset,
                      url       : doc.url,
                      steps     : steps_to_html(doc.steps),
                      exitstatus: doc.exitstatus,
                      reproduced: doc.reproduced,
                      attachments: attachments_to_html(doc)
                    });
  if (doc.type == 'result_header_unittest')
    return template(templates.unittest_result, {
                      result_id : doc._id,
                      test      : doc.test,
                      extra_test_args: doc.extra_test_args,
                      product   : doc.product,
                      branch    : doc.branch,
                      buildtype : doc.buildtype,
                      os_name   : doc.os_name,
                      os_version: doc.os_version,
                      cpu_name  : doc.cpu_name,
                      datetime  : doc.datetime,
                      changeset : doc.changeset,
                      exitstatus : doc.exitstatus,
                      returncode: doc.returncode,
                      attachments: attachments_to_html(doc)
                    });
}

