function (doc) {
  if (doc.type == "tests") {
    emit(doc._id, doc);
  }
}
