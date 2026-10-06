import {
  Activity,
  Database,
  FileSearch,
  LayoutDashboard,
  LogOut,
  Radar,
  Settings2,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { api, post, setCsrf } from "./api";
import { Empty, Loading } from "./components/ui";
import Sources from "./pages/Sources";

import Evaluation from "./pages/Evaluation";
import IncidentDetail from "./pages/IncidentDetail";
import Incidents from "./pages/Incidents";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import SettingsPage from "./pages/SettingsPage";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}
export default function App() {
  const [user, setUser] = useState<{
      email: string;
      read_only?: boolean;
    } | null>(null),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    api<{ email: string; csrf_token: string; read_only: boolean }>("/auth/me")
      .then((value) => {
        setUser(value);
        setCsrf(value.csrf_token);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    const expire = () => setUser(null);
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, []);
  if (loading) return <Loading />;
  if (!user) return <Login onLogin={setUser} />;
  return (
    <BrowserRouter>
      <ScrollToTop />
      <div className="app-shell">
        <aside className="sidebar">
          <Link className="brand" to="/">
            <span className="brand-icon">
              <Radar size={25} />
            </span>
            <span>
              LeakLens<span className="brand-ai">AI</span>
            </span>
          </Link>
          <div className="workspace-chip">
            <span className="status-dot" /> Analyst workspace
          </div>
          <div className="nav-label">INVESTIGATE</div>
          <nav>
            <NavLink to="/" end>
              <LayoutDashboard size={18} /> Overview
            </NavLink>
            <NavLink to="/incidents">
              <FileSearch size={18} /> Incidents
            </NavLink>
            <NavLink to="/sources">
              <Database size={18} /> Sources
            </NavLink>
            <NavLink to="/evaluation">
              <Activity size={18} /> Evaluation
            </NavLink>
          </nav>
          <div className="nav-label">WORKSPACE</div>
          <nav>
            <NavLink to="/settings">
              <Settings2 size={18} /> Settings
            </NavLink>
          </nav>
          <div className="sidebar-bottom">
            <div className="privacy-note">
              <ShieldCheck size={20} />
              <div>
                Evidence first<span>Redacted by default</span>
              </div>
            </div>
            <div className="user">
              <span className="avatar">{user.email[0].toUpperCase()}</span>
              <span className="user-email">
                {user.email}
                <small>Analyst</small>
              </span>
              <button
                className="icon-button"
                aria-label="Sign out"
                onClick={async () => {
                  await post("/auth/logout");
                  setUser(null);
                }}
              >
                <LogOut size={17} />
              </button>
            </div>
          </div>
        </aside>
        <div className="main">
          <div className="topbar">
            <span>Exposure investigation platform</span>
            <div>
              <span className="status-dot" />{" "}
              {user.read_only ? "Read-only workspace" : "Private workspace"}
              <span className="topbar-divider" />
              <ShieldCheck size={16} /> Authorized sources only
            </div>
          </div>
          <main>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/sources" element={<Sources />} />
              <Route path="/incidents" element={<Incidents />} />
              <Route path="/incidents/:id" element={<IncidentDetail />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/evaluation" element={<Evaluation />} />
              <Route
                path="*"
                element={
                  <Empty title="Page not found">
                    <Link to="/">Return to overview</Link>
                  </Empty>
                }
              />
            </Routes>
          </main>
          <footer>
            LeakLens AI{" "}
            <span>
              Independent research & engineering project · Evidence requires
              analyst review
            </span>
          </footer>
        </div>
      </div>
    </BrowserRouter>
  );
}
