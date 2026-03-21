import { useState } from "react";

type Props = {
  error: string | null;
  busy: boolean;
  onSubmit: (payload: { username: string; password: string }) => Promise<void>;
};

export function LoginPanel({ error, busy, onSubmit }: Props) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123!");

  return (
    <main className="login-screen">
      <section className="login-card">
        <div className="login-eyebrow">TRADER&apos;S / COCKPIT</div>
        <h1 className="login-title">Session Required</h1>
        <p className="login-copy">
          Sign in to load account state and execute protected trade actions.
        </p>
        <form
          className="login-form"
          onSubmit={(event) => {
            event.preventDefault();
            void onSubmit({ username, password });
          }}
        >
          <label className="login-field">
            <span className="login-label">Username</span>
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          </label>
          <label className="login-field">
            <span className="login-label">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error ? <div className="login-error">{error}</div> : null}
          <button type="submit" className="btn btn-cyan login-submit" disabled={busy}>
            {busy ? "SIGNING IN..." : "SIGN IN"}
          </button>
        </form>
      </section>
    </main>
  );
}
