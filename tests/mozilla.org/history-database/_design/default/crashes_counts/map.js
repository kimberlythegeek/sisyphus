
function (doc) {
  if (doc.type == 'crash') {
    emit([doc.crash, doc.crashsignature], 1);
  }
}
