function (doc) {
  if (doc.type == 'result_assertion') {
    emit([doc.assertion, doc.assertionfile], 1);
  }
}
