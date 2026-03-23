import type { AccountView, AuthUser } from "@/lib/types";
import { phaseLabel } from "@/lib/cockpit-ui";

type Props = {
  phase: string;
  account: AccountView | null;
  authUser: AuthUser | null;
  onLogout: () => void;
};

export function CockpitHeader(props: Props) {
  const {
    phase,
    account,
    authUser,
    onLogout
  } = props;
  return (
    <div className="header">
      <div className="logo">
        TRADER&apos;S <span>/ COCKPIT</span>
      </div>
      <div className="badge badge-paper">{account?.effective_mode?.includes("live") ? "LIVE" : "\u25CF PAPER"}</div>
      <div className={`state-display state-${phase}`}>{phaseLabel(phase)}</div>
      {authUser ? (
        <div className="auth-strip auth-strip-end">
          <div className="auth-user">
            {authUser.username}
            <span>{authUser.role}</span>
          </div>
          <button type="button" className="btn btn-ghost auth-logout-btn" onClick={onLogout}>
            LOGOUT
          </button>
        </div>
      ) : null}
    </div>
  );
}
