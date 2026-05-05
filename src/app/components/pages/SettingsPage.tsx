import React, { useEffect, useMemo, useState } from "react";
import { Clock, RefreshCw, Moon, Sun, Bell, Shield } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { DEFAULT_SETTINGS, SettingsState, ThemeMode, useSettings } from "../../contexts/SettingsContext";

export const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const { settings, loading, saveSettings } = useSettings();

  const [refreshRate, setRefreshRate] = useState(DEFAULT_SETTINGS.refreshRate);
  const [sessionTimeout, setSessionTimeout] = useState(DEFAULT_SETTINGS.sessionTimeout);
  const [theme, setTheme] = useState<ThemeMode>(DEFAULT_SETTINGS.theme);
  const [notifications, setNotifications] = useState(DEFAULT_SETTINGS.notifications);
  const [initialSettings, setInitialSettings] = useState<SettingsState>(DEFAULT_SETTINGS);
  const [saving, setSaving] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [statusError, setStatusError] = useState(false);

  const currentSettings: SettingsState = useMemo(
    () => ({
      refreshRate,
      sessionTimeout,
      theme,
      notifications,
    }),
    [refreshRate, sessionTimeout, theme, notifications]
  );

  const hasChanges = useMemo(() => {
    return JSON.stringify(currentSettings) !== JSON.stringify(initialSettings);
  }, [currentSettings, initialSettings]);

  useEffect(() => {
    setRefreshRate(settings.refreshRate);
    setSessionTimeout(settings.sessionTimeout);
    setTheme(settings.theme);
    setNotifications(settings.notifications);
    setInitialSettings(settings);
  }, [settings]);

  const handleSaveSettings = async () => {
    if (!user?.uid) return;

    setSaving(true);
    setStatusText("");
    setStatusError(false);

    try {
      await saveSettings(currentSettings);
      setInitialSettings(currentSettings);
      setStatusText("Settings saved successfully.");
      setStatusError(false);
    } catch (error) {
      console.error("Failed to save settings:", error);
      setStatusText("Failed to save settings. Please try again.");
      setStatusError(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl text-gray-900 mb-2">Settings</h1>
        <p className="text-gray-600">Configure application preferences and system settings</p>
      </div>

      {/* Settings Sections */}
      <div className="space-y-6">
        {/* System Settings */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-4 flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-emerald-600" />
            System Settings
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-700 mb-2">
                Auto-Refresh Rate (seconds)
              </label>
              <select
                value={refreshRate}
                onChange={(e) => setRefreshRate(e.target.value)}
                disabled={loading || saving}
                className="w-full max-w-md px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="5">5 seconds</option>
                <option value="10">10 seconds (Recommended)</option>
                <option value="30">30 seconds</option>
                <option value="60">60 seconds</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Controls how often the real-time monitoring page updates
              </p>
            </div>
          </div>
        </div>

        {/* Session Settings */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-emerald-600" />
            Session Settings
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-700 mb-2">
                Session Timeout (minutes)
              </label>
              <select
                value={sessionTimeout}
                onChange={(e) => setSessionTimeout(e.target.value)}
                disabled={loading || saving}
                className="w-full max-w-md px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="15">15 minutes</option>
                <option value="30">30 minutes (Recommended)</option>
                <option value="60">60 minutes</option>
                <option value="120">120 minutes</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Automatically logout after this period of inactivity
              </p>
            </div>
          </div>
        </div>

        {/* Appearance Settings */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-4 flex items-center gap-2">
            {theme === 'light' ? (
              <Sun className="w-5 h-5 text-emerald-600" />
            ) : (
              <Moon className="w-5 h-5 text-emerald-600" />
            )}
            Appearance
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-700 mb-2">Theme</label>
              <div className="flex gap-3">
                <button
                  onClick={() => setTheme('light')}
                  disabled={loading || saving}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
                    theme === 'light'
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                      : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <Sun className="w-4 h-4" />
                  Light
                </button>
                <button
                  onClick={() => setTheme('dark')}
                  disabled={loading || saving}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
                    theme === 'dark'
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-700'
                      : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <Moon className="w-4 h-4" />
                  Dark
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Note: Dark theme is currently in development
              </p>
            </div>
          </div>
        </div>

        {/* Notification Settings */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-4 flex items-center gap-2">
            <Bell className="w-5 h-5 text-emerald-600" />
            Notifications
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-900">Enable Notifications</p>
                <p className="text-xs text-gray-500">
                  Receive alerts for critical faults and system issues
                </p>
              </div>
              <button
                onClick={() => setNotifications(!notifications)}
                disabled={loading || saving}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  notifications ? 'bg-emerald-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    notifications ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>
        </div>

        {/* Security Info */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h2 className="text-lg text-gray-900 mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-emerald-600" />
            Security Information
          </h2>
          <div className="space-y-3">
            <div className="flex items-start gap-3 p-3 bg-emerald-50 rounded-lg">
              <Shield className="w-5 h-5 text-emerald-600 mt-0.5" />
              <div>
                <p className="text-sm text-emerald-900">Secure Connection</p>
                <p className="text-xs text-emerald-700">
                  All data is transmitted over encrypted HTTPS connections
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
              <Shield className="w-5 h-5 text-blue-600 mt-0.5" />
              <div>
                <p className="text-sm text-blue-900">Role-Based Access Control</p>
                <p className="text-xs text-blue-700">
                  Access to sensitive features is restricted based on user role
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-purple-50 rounded-lg">
              <Shield className="w-5 h-5 text-purple-600 mt-0.5" />
              <div>
                <p className="text-sm text-purple-900">Session Management</p>
                <p className="text-xs text-purple-700">
                  Sessions automatically expire after configured timeout period
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex items-center justify-between gap-4">
          <p
            className={`text-sm ${
              statusError ? "text-red-600" : "text-emerald-700"
            }`}
          >
            {loading ? "Loading settings from backend..." : statusText}
          </p>
          <button
            onClick={handleSaveSettings}
            disabled={loading || saving || !hasChanges || !user?.uid}
            className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <p className="text-sm text-gray-700">
          <strong>Important:</strong> TechBin Dashboard is designed for internal organizational
          use only. This system should not be used for collecting personally identifiable
          information (PII) or handling sensitive user data.
        </p>
      </div>
    </div>
  );
};
