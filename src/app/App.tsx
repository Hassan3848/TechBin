import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { SettingsProvider } from './contexts/SettingsContext';
import { LoginPage } from './components/LoginPage';
import { DashboardLayout } from './components/DashboardLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { DashboardOverview } from './components/pages/DashboardOverview';
import { AnalyticsPage } from './components/pages/AnalyticsPage';
import { RealTimeMonitoringPage } from './components/pages/RealTimeMonitoringPage';
import { FaultDetectionPage } from './components/pages/FaultDetectionPage';
import { BinHealthStatusPage } from './components/pages/BinHealthStatusPage';
import { UserManagementPage } from './components/pages/UserManagementPage';
import { SettingsPage } from './components/pages/SettingsPage';
import BinRegistryPage from "./components/pages/BinRegistryPage";

export default function App() {
  return (
    <AuthProvider>
      <SettingsProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Route */}
            <Route path="/" element={<LoginPage />} />

            {/* Protected Dashboard Routes */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<DashboardOverview />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="monitoring" element={<RealTimeMonitoringPage />} />
              <Route path="faults" element={<FaultDetectionPage />} />
              <Route path="health" element={<BinHealthStatusPage />} />

              {/* ✅ Bins: allow ALL signed-in users (Viewer can view, Admin can edit, SuperAdmin can create/delete) */}
              <Route
                path="bins"
                element={
                  <ProtectedRoute>
                    <BinRegistryPage />
                  </ProtectedRoute>
                }
              />

              {/* ✅ Admin-only */}
              <Route
                path="users"
                element={
                  <ProtectedRoute requireAdmin>
                    <UserManagementPage />
                  </ProtectedRoute>
                }
              />

              <Route path="settings" element={<SettingsPage />} />
            </Route>

            {/* Catch all - redirect to login */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </SettingsProvider>
    </AuthProvider>
  );
}
