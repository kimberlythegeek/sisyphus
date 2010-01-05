function (doc) {
  if (doc.type == 'result' && doc.reproduced && !doc.triage) {
    emit(doc.datetime, doc);
  }
}