import { Navigate, Route, Routes } from 'react-router';
import { LoginPage } from './auth/LoginPage.tsx';
import { RequireAuth } from './auth/RequireAuth.tsx';
import { StopListPage } from './menu/StopListPage.tsx';
import { QueuePage } from './orders/QueuePage.tsx';
import { TodayPage } from './orders/TodayPage.tsx';
import { Layout } from './ui/Layout.tsx';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<QueuePage />} />
          <Route path="today" element={<TodayPage />} />
          <Route path="menu" element={<StopListPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
