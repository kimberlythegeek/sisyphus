function retest_results(evt) {

  var signature = '';
  var button_element = evt.target;
  if (button_element)
    signature = button_element.getAttribute('signature').replace(/[\s\n]+/g, ' ');

  // collect the urls to be retested by grabbing the links with class 'url'
  var urllinks = document.getElementsByClassName('url');
  var urlhash  = {};
  var urls     = [];
  for each (var urllink in urllinks)
    if (urllink.href) {
      if (!(urllink.href in urlhash)) {
        urlhash[urllink.href] = 1;
        urls.push(urllink.href);
      }
    }

  var operating_systems = {};

  var db                    = new CouchDB('sisyphus');
  var branches_doc          = db.open('branches');
  var matching_workers_view = db.view('crashtest/matching_workers');

  for each (var matching_worker in matching_workers_view.rows) {

    var os_name    = matching_worker.key[0];
    var os_version = matching_worker.key[1];
    var cpu_name   = matching_worker.key[2];

    if (!(os_name in operating_systems))
      operating_systems[os_name] = {};

    if (!(os_version in operating_systems[os_name]))
      operating_systems[os_name][os_version] = {};

    if (!(cpu_name in operating_systems[os_name][os_version]))
      operating_systems[os_name][os_version][cpu_name] = 1;

  }

  for (var major_version in branches_doc['version_to_branch']) {

    var minor_version = major_version;

    for (os_name in operating_systems) {

      for (os_version in operating_systems[os_name]) {

        for (cpu_name in operating_systems[os_name][os_version]) {

          // PowerPC is not supported after Firefox 3.6
          if (major_version > '0306' && cpu_name == 'ppc')
            continue;

          signature_doc                   = {};
          signature_doc['type']           = 'signature';
          signature_doc['major_version']  = major_version;
          signature_doc['os_name']        = os_name;
          signature_doc['os_version']     = os_version;
          signature_doc['cpu_name']       = cpu_name;
          signature_doc['urls']           = urls;
          signature_doc['date']           = null;
          signature_doc['signature']      = signature.trim();
          signature_doc['bug_list']       = null;
          signature_doc['worker']         = null;
          signature_doc['processed_by']   = {};
          signature_doc['priority']       = '1';  // priority 0 will be processed first.

          try {
            db.save(signature_doc);
          }
          catch(ex) {
            alert('Exception ' + ex + ' creating signature ' + signature_doc.toSource());
          }

        }
      }
    }
  }
  var new_element = document.createElement('span');
  new_element.innerHTML = 'urls submitted';
  button_element.parentNode.replaceChild(new_element, button_element);

  return false;
}
