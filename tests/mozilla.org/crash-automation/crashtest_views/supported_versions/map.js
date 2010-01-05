function(doc) {
  if (doc.type == "supported_versions")
    emit(null, doc);
}
