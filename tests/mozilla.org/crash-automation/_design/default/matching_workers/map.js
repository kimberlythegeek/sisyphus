function (doc) {
  if (doc.type == "worker" && ! /(disabled|zombie)/.exec(doc.state)) {
    emit([doc.os_name, doc.os_version, doc.cpu_name], {worker_id: doc._id})
  }
}
