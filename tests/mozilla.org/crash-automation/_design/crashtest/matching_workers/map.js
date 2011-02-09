function (doc) {
  try
  {
    var reWorkerState = new RegExp('(disabled|zombie)');
    if (doc.type == "worker_crashtest" && ! reWorkerState.exec(doc.state)) {
      emit([doc.os_name, doc.os_version, doc.cpu_name], {worker_id: doc._id});
    }
  }
  catch(ex)
  {
  }
}
