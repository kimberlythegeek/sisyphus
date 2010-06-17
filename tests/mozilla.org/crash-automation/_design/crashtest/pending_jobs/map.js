function(doc) {
  if (doc.type == 'signature' && !doc.worker)
    emit([
           doc.priority ? doc.priority : '1',  // 0..9 - highest to lowest priority
           doc.os_name,
           doc.cpu_name,
           doc.os_version,
           Math.round(-doc.urls.length) // sort by descending url count
         ],
         {
           signature_id: doc._id
         });
}
