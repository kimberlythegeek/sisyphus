/*
when    - datetime
where   - [product, branch, buildtype]
what    - [test, extra_test_args]
who     - [os_name, os_version, cpu_name, worker_id]
value   - [url]

key [when, who, where, what, value, seq]
*/

function (doc) {
  switch(doc.type) {
  case 'result':
    emit([doc._id, doc.type], null);
    break;
  case 'result_crash':
  case 'result_valgrind':
  case 'result_assertion':
    emit([doc.result_id, doc.type], null);
    break;
  }
}
