function (doc) {
  if (doc.type == 'assertion') {
    emit([doc.assertion, doc.assertionfile], 1);
  }
}
