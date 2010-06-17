function (doc, request) {
  // !json templates.result
  // !code vendor/couchapp/path.js
  // !code vendor/couchapp/date.js
  // !code vendor/couchapp/template.js

  function attachments_to_html(attachments) {
    var s = '';
    var attachment_list = [];
    for (var filename in attachments) {
      attachment_list.push(filename);
    }
    attachment_list.sort();
    for (var i = 0; i < attachment_list.length; i++) {
      filename = attachment_list[i];
      s += '<li><a href="/unittest/' + doc._id + '/' + filename + '">' + filename + '</a></li>';
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

  return template(templates.result, {
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
                    attachments: attachments_to_html(doc._attachments)
                  });
}
