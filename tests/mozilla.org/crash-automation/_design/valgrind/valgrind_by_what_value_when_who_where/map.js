/*
when    - datetime
where   - [product, branch, buildtype]
what    - [test, extra_test_args]
who     - [os_name, os_version, cpu_name, worker_id]
value   - [valgrind]

key [what, value, when, who, where]
*/

function (doc) {
  function key() {
    var dict = { when  : [doc.datetime],
                 where : [doc.product, doc.branch, doc.buildtype],
                 what  : [doc.test, doc.extra_test_args],
                 who   : [doc.os_name, doc.os_version, doc.cpu_name, doc.worker_id]
               };
    var keyvalue = [];
    for (var i = 0; i < arguments.length; i++) {
      var arg = arguments[i];
      if (arg in dict)
        keyvalue = keyvalue.concat(dict[arg]);
      else
        keyvalue.push(arg);
    }
    return keyvalue;
  }
  if (doc.type == 'result_valgrind') {
    emit(key('what', doc.valgrind, 'when', 'who', 'where'), null);
  }
}