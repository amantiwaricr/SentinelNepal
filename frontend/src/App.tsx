import { Route, Routes } from 'react-router'

import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth, RequireRole } from './auth/RequireAuth'
import { AppLayout } from './layouts/AppLayout'
import { AlertDetailsPage } from './pages/AlertDetailsPage'
import { AlertsPage } from './pages/AlertsPage'
import { AuditLogsPage } from './pages/AuditLogsPage'
import { DashboardPage } from './pages/DashboardPage'
import { DatasetAnalysisPage } from './pages/DatasetAnalysisPage'
import { FirewallPage } from './pages/FirewallPage'
import { FirewallRequestPage } from './pages/FirewallRequestPage'
import { IncidentDetailPage } from './pages/IncidentDetailPage'
import { IncidentsPage } from './pages/IncidentsPage'
import { IpInvestigationPage } from './pages/IpInvestigationPage'
import { LoginPage } from './pages/LoginPage'
import { ModelEvaluationPage } from './pages/ModelEvaluationPage'
import { NewFirewallRequestPage } from './pages/NewFirewallRequestPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { SystemHealthPage } from './pages/SystemHealthPage'

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="alerts/:alertId" element={<AlertDetailsPage />} />
          <Route path="ips" element={<IpInvestigationPage />} />
          <Route path="incidents" element={<IncidentsPage />} />
          <Route path="incidents/:incidentId" element={<IncidentDetailPage />} />
          <Route path="recommendations" element={<RecommendationsPage />} />
          <Route path="firewall" element={<FirewallPage />} />
          <Route path="firewall/new" element={<NewFirewallRequestPage />} />
          <Route path="firewall/:requestId" element={<FirewallRequestPage />} />
          <Route path="datasets" element={<DatasetAnalysisPage />} />
          <Route path="model" element={<ModelEvaluationPage />} />
          <Route
            path="audit"
            element={
              <RequireRole role="admin">
                <AuditLogsPage />
              </RequireRole>
            }
          />
          <Route path="system" element={<SystemHealthPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
