
function (doc) {
  if (doc.type == 'result_crash') {
    emit([doc.crash, doc.crashsignature], 1);
  }
}
