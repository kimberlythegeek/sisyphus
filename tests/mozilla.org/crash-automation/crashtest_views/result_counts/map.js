function(doc) {
  if (doc.type == 'result') {
        //emit(null, doc)
        //emit(null, {"signature": doc.signature, "url" : doc.url, "reproduced" : doc.reproduced, "worker_id" : doc.worker_id});
        emit('total results', 1);
        emit(doc.reproduced ? "crashed" : "normal" , 1);
        if (doc.exitstatus == 'TIMED OUT')
            emit('timed out', 1);
  }
}