user_pref("app.update.enabled", false);
user_pref("browser.dom.window.dump.enabled", true);
user_pref("dom.disable_beforeunload", true);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("capability.policy.policynames", "trusted");
user_pref("capability.policy.trusted.sites", "http://test.mozilla.com http://test.bclary.com");
user_pref("capability.principal.codebase.p0.granted", "UniversalPreferencesWrite UniversalXPConnect UniversalBrowserWrite UniversalPreferencesRead UniversalBrowserRead");
user_pref("capability.principal.codebase.p0.id", "http://test.mozilla.com");
user_pref("capability.principal.codebase.p1.granted", "UniversalPreferencesWrite UniversalXPConnect UniversalBrowserWrite UniversalPreferencesRead UniversalBrowserRead");
user_pref("capability.principal.codebase.p1.id", "http://test.bclary.com");
user_pref("dom.allow_scripts_to_close_windows", true);
user_pref("dom.max_script_run_time", 1800);
user_pref("dom.max_chrome_script_run_time", 1800);
user_pref("extensions.update.enabled", false);
user_pref("extensions.update.notifyUser", false);
user_pref("javascript.allow.mailnews", true);
user_pref("mail.startup.enabledMailCheckOnce", false);
user_pref("security.enable_java", false);
user_pref("security.warn_submit_insecure", false);
user_pref("signed.applets.codebase_principal_support", true);
user_pref("mailnews.start_page.override_url", "http://test.mozilla.com/bin/install-extensions-1.html");
user_pref("mailnews.start_page.url", "http://test.mozilla.com/bin/install-extensions-1.html");
user_pref("mailnews.start_page.welcome_url", "http://test.mozilla.com/bin/install-extensions-1.html");
user_pref("browser.warnOnQuit", false);
user_pref("extensions.checkCompatibility", false);
user_pref("extensions.checkUpdateSecurity", false);
user_pref("browser.EULA.override", true);
user_pref("extensions.autoDisableScopes", 10);
user_pref("toolkit.startup.max_resumed_crashes", -1);
user_pref("network.proxy.type", 5);
user_pref("xpinstall.signatures.required", false);
user_pref("hangmonitor.timeout", 0); // no hang monitor
//https://dxr.mozilla.org/mozilla-central/source/toolkit/components/terminator/nsTerminator.cpp#50
//https://dxr.mozilla.org/mozilla-central/source/toolkit/components/terminator/nsTerminator.cpp#364
user_pref("toolkit.asyncshutdown.crash_timeout", 240000);
