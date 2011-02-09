function(doc) {
  if (doc.type == 'signature' && !doc.worker) {
    try {
      emit([ doc.priority ? doc.priority : '3', doc.os_name, doc.cpu_name, doc.os_version, -doc.urls.length ], { signature_id: doc._id });
    }
    catch(ex) {
    }
  }
}
