import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuthStore } from "../features/auth/authStore";

export function RequireAuth() {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
