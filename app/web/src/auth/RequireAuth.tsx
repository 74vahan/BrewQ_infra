import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth, useSessionLifecycle } from './useAuth.ts';

/** Layout route: signed-in barista sees the children, anyone else goes to /login. */
export function RequireAuth() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  useSessionLifecycle();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
