import { Route, Routes } from 'react-router'

import { AppLayout } from './layouts/AppLayout'
import { AlertDetailsPage } from './pages/AlertDetailsPage'
import { AlertsPage } from './pages/AlertsPage'
import { AuditLogsPage } from './pages/AuditLogsPage'
import { DashboardPage } from './pages/DashboardPage'
import { FirewallPage } from './pages/FirewallPage'
import { IncidentsPage } from './pages/IncidentsPage'
import { IpInvestigationPage } from './pages/IpInvestigationPage'
import { LoginPage } from './pages/LoginPage'
import { ModelEvaluationPage } from './pages/ModelEvaluationPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { SystemHealthPage } from './pages/SystemHealthPage'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="alerts/:alertId" element={<AlertDetailsPage />} />
        <Route path="ips" element={<IpInvestigationPage />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route path="recommendations" element={<RecommendationsPage />} />
        <Route path="firewall" element={<FirewallPage />} />
        <Route path="audit" element={<AuditLogsPage />} />
        <Route path="model" element={<ModelEvaluationPage />} />
        <Route path="system" element={<SystemHealthPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
