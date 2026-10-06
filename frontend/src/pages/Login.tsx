import { ArrowRight, Fingerprint, Radar } from "lucide-react";
import { useState, type FormEvent } from "react";
import { post, setCsrf } from "../api";
import { Button, ErrorMessage } from "../components/ui";

export default function Login({
  onLogin,
}: {
  onLogin: (user: { email: string }) => void;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const values = new FormData(e.currentTarget);
    try {
      const result = await post<{ email: string; csrf_token: string }>(
        "/auth/login",
        Object.fromEntries(values),
      );
      setCsrf(result.csrf_token);
      onLogin(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <div className="login-art">
        <div className="brand">
          <Radar size={32} /> LeakLens<span className="brand-ai">AI</span>
        </div>
        <div>
          <span className="eyebrow">CLARITY IN EVERY FINDING</span>
          <h1>
            From exposed data
            <br />
            to informed action.
          </h1>
          <p>
            Trace the evidence. Understand the context.
            <br />
            Keep the analyst in control.
          </p>
          <div className="radar-art">
            <span />
            <span />
            <span />
            <Fingerprint size={70} />
          </div>
        </div>
        <small>Independent branding. Authorized investigations.</small>
      </div>
      <div className="login-side">
        <form className="login-form" onSubmit={submit}>
          <span className="eyebrow">YOUR INVESTIGATION WORKSPACE</span>
          <h1>Welcome back.</h1>
          <p>Sign in to review your sources and findings.</p>
          <ErrorMessage message={error} />
          <label>
            Email
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
              placeholder="analyst@your-company.com"
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <Button className="primary full" busy={busy}>
            Sign in <ArrowRight size={17} />
          </Button>
          <p className="small muted">
            Use the analyst account created during local setup. No default
            credentials are included.
          </p>
        </form>
      </div>
    </div>
  );
}
