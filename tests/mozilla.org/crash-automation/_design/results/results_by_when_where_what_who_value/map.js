/*
when    - datetime
where   - [product, branch, buildtype]
what    - [test, extra_test_args]
who     - [os_name, os_version, cpu_name, worker_id]
value   - [url]

key [when, who, where, what, value, seq]
*/

function (doc) {
  function key() {
    var dict = { when  : [doc.datetime],
                 where : [doc.product, doc.branch, doc.buildtype],
                 what  : [doc.test, doc.extra_test_args],
                 who   : [doc.os_name, doc.os_version, doc.cpu_name, doc.worker_id],
                 value : [doc.location_id]
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
  switch(doc.type) {
  case 'result':
    emit(key('when', 'who', 'where', 'what', doc.type), null);
    break;
  case 'result_crash':
    emit(key('when', 'who', 'where', 'what', doc.type, 'value', doc.crash), null);
    break;
  case 'result_valgrind':
    emit(key('when', 'who', 'where', 'what', doc.type, 'value', doc.valgrind), null);
    break;
  case 'result_assertion':
    emit(key('when', 'who', 'where', 'what', doc.type, 'value', doc.assertion), null);
    break;
  }
}
