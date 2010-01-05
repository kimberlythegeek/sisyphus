function(doc) {

  function days(ccyymmdd) {
    return new Date(ccyymmdd.slice(0,4) + '/' + ccyymmdd.slice(4,6) + '/' + ccyymmdd.slice(6,8)).getTime()/86400000;
  }

  if (doc.type == 'signature' && !doc.worker)
    emit([
           doc.priority ? doc.priority : '1',  // 0..9 - highest to lowest priority
           doc.os_name,
           doc.cpu_name,
           doc.os_version,
//           Math.round(-days(doc.date)-doc.urls.length), // sort by descending date, descending url count
           Math.round(-doc.urls.length), // sort by descending url count
         ],
         {
           signature_id: doc._id
         });
}