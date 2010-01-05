function (doc) {
  if (doc.type == 'result') {
    emit(doc.worker_id, 1);
  }
}