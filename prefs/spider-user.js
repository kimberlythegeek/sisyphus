user_pref("app.update.enabled", false);
user_pref("browser.dom.window.dump.enabled", true);
user_pref("dom.disable_beforeunload", true);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.xul.error_pages.enabled", true);
user_pref("dom.allow_scripts_to_close_windows", true);
user_pref("dom.disable_open_during_load", false);
user_pref("dom.max_script_run_time", 1800);
user_pref("dom.max_chrome_script_run_time", 1800);
user_pref("javascript.allow.mailnews", true);
user_pref("javascript.options.showInConsole", true);
user_pref("layout.css.report_errors", true);
user_pref("security.enable_java", true);
user_pref("security.warn_entering_secure", false);
user_pref("security.warn_entering_weak", false);
user_pref("security.warn_leaving_secure", false);
user_pref("security.warn_submit_insecure", false);
user_pref("security.warn_viewing_mixed", false);
user_pref("browser.warnOnQuit", false);
user_pref("browser.cache.check_doc_frequency", 1);
user_pref("extensions.checkCompatibility", false);
user_pref("extensions.checkUpdateSecurity", false);
user_pref("browser.EULA.override", true);
user_pref("toolkit.startup.max_resumed_crashes", -1);
user_pref("extensions.autoDisableScopes", 10);
user_pref("network.proxy.type", 5);
user_pref("xpinstall.signatures.required", false);
user_pref("hangmonitor.timeout", 0); // no hang monitor
//https://dxr.mozilla.org/mozilla-central/source/toolkit/components/terminator/nsTerminator.cpp#50
//https://dxr.mozilla.org/mozilla-central/source/toolkit/components/terminator/nsTerminator.cpp#364
user_pref("toolkit.asyncshutdown.crash_timeout", 240000);
