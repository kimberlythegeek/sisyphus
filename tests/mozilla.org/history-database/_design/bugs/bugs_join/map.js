function(doc) {
  var i;
  var bug_list;
  var len;

  switch(doc.type)
  {
  case 'assertion':
    if (doc.bug_list) {
      bug_list = doc.bug_list;
      var states = {
        'open' : 1, 'closed' : 1
      };
      for (state in states) {
        len = bug_list[state].length;
        for (i = 0; i < len; i++) {
          emit([bug_list[state][i], doc.type, doc.assertion, doc.assertionfile, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], 1);
        }
      }
    }
    break;
  case 'valgrind':
    if (doc.bug_list) {
      bug_list = doc.bug_list;
      var states = {
        'open' : 1, 'closed' : 1
      };
      for (state in states) {
        len = bug_list[state].length;
        for (i = 0; i < len; i++) {
          emit([bug_list[state][i], doc.type, doc.valgrind, doc.valgrindsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], 1);
        }
      }
    }
    break;
  case 'crash':
    if (doc.bug_list) {
      bug_list = doc.bug_list;
      var states = {
        'open' : 1, 'closed' : 1
      };
      for (state in states) {
        len = bug_list[state].length;
        for (i = 0; i < len; i++) {
          emit([bug_list[state][i], doc.type, doc.crash, doc.crashsignature, doc.product, doc.branch, doc.buildtype, doc.os_name, doc.os_version, doc.cpu_name], 1);
        }
      }
    }
    break;
  }
}