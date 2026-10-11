import { Navigate, Route, Routes } from "react-router";

import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { InternsPage } from "./pages/InternsPage";
import { InternshipPage } from "./pages/internship/InternshipPage";
import { InternshipsPage } from "./pages/InternshipsPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SupervisorsPage } from "./pages/SupervisorsPage";

export function App() {
  return (
    <Routes>
      <Route path="/connexion" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/stages" replace />} />
          <Route path="stages" element={<InternshipsPage />} />
          <Route path="stages/:internshipId" element={<InternshipPage />} />
          <Route path="stagiaires" element={<InternsPage />} />
          <Route path="encadrants" element={<SupervisorsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
