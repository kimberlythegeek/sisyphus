// And scan for changes at startup
// By default don't disable add-ons from any scope
// http://searchfox.org/mozilla-central/source/toolkit/mozapps/extensions/internal/AddonTestUtils.jsm#254
//By default load extensions from all scopes except temporary.
user_pref("app.update.enabled", false);
user_pref("browser.EULA.override", true);
user_pref("browser.dom.window.dump.enabled", true);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.tabs.remote.autostart", true);
user_pref("browser.tabs.remote.force-enable", true);
user_pref("browser.warnOnQuit", false);
user_pref("capability.policy.policynames", "trusted");
user_pref("capability.policy.trusted.sites", "http://test.mozilla.com http://test.bclary.com");
user_pref("capability.principal.codebase.p0.granted", "UniversalPreferencesWrite UniversalXPConnect UniversalBrowserWrite UniversalPreferencesRead UniversalBrowserRead");
user_pref("capability.principal.codebase.p0.id", "http://test.mozilla.com");
user_pref("capability.principal.codebase.p1.granted", "UniversalPreferencesWrite UniversalXPConnect UniversalBrowserWrite UniversalPreferencesRead UniversalBrowserRead");
user_pref("capability.principal.codebase.p1.id", "http://test.bclary.com");
user_pref("dom.allow_scripts_to_close_windows", true);
user_pref("dom.disable_beforeunload", true);
user_pref("dom.max_chrome_script_run_time", 1800);
user_pref("dom.max_script_run_time", 1800);
user_pref("extensions.autoDisableScopes", 0);
user_pref("extensions.checkCompatibility", false);
user_pref("extensions.checkUpdateSecurity", false);
user_pref("extensions.enabledScopes", 5);
user_pref("extensions.startupScanScopes", 5);
user_pref("extensions.update.enabled", false);
user_pref("extensions.update.notifyUser", false);
user_pref("hangmonitor.timeout", 0); // no hang monitor
user_pref("javascript.allow.mailnews", true);
user_pref("mail.startup.enabledMailCheckOnce", false);
user_pref("mailnews.start_page.override_url", "http://test.mozilla.com/bin/install-extensions-1.html");
user_pref("mailnews.start_page.url", "http://test.mozilla.com/bin/install-extensions-1.html");
user_pref("mailnews.start_page.welcome_url", "http://test.mozilla.com/bin/install-extensions-1.html");
user_pref("network.proxy.backup.ftp", "proxy.bughunter.ateam.scl3.mozilla.com");
user_pref("network.proxy.backup.ftp_port", 3128);
user_pref("network.proxy.backup.socks", "proxy.bughunter.ateam.scl3.mozilla.com");
user_pref("network.proxy.backup.socks_port", 3128);
user_pref("network.proxy.backup.ssl", "proxy.bughunter.ateam.scl3.mozilla.com");
user_pref("network.proxy.backup.ssl_port", 3128);
user_pref("network.proxy.ftp", "proxy.bughunter.ateam.scl3.mozilla.com");
user_pref("network.proxy.ftp_port", 3128);
user_pref("network.proxy.http", "proxy.bughunter.ateam.scl3.mozilla.com");
user_pref("network.proxy.http_port", 3128);
user_pref("network.proxy.no_proxies_on", "localhost,127.0.0.1,localaddress,.localdomain.com, 10.0.0.0/8, *.scl3.mozilla.com, *.scl3.mozilla.com, 169.254.169.254");
user_pref("network.proxy.share_proxy_settings", true);
user_pref("network.proxy.socks", "proxy.bughunter.ateam.scl3.mozilla.com");
user_pref("network.proxy.socks_port", 3128);
user_pref("network.proxy.socks_remote_dns", true);
user_pref("network.proxy.ssl", "proxy.bughunter.ateam.scl3.mozilla.com");
user_pref("network.proxy.ssl_port", 3128);
user_pref("network.proxy.type", 1)
user_pref("security.enable_java", false);
user_pref("security.warn_submit_insecure", false);
user_pref("signed.applets.codebase_principal_support", true);
user_pref("toolkit.asyncshutdown.crash_timeout", 240000);
user_pref("toolkit.startup.max_resumed_crashes", -1);
user_pref("toolkit.telemetry.server", "");
user_pref("toolkit.telemetry.unified", false);
user_pref("xpinstall.signatures.required", false);
// http://searchfox.org/mozilla-central/source/toolkit/xre/nsAppRunner.cpp#5007
user_pref("extensions.e10sBlocksEnabling", false);
user_pref("extensions.e10sBlockedByAddons", false);
user_pref("extensions.e10sMultiBlockedByAddons", false);
user_pref("extensions.e10s.rollout.policy", "");
