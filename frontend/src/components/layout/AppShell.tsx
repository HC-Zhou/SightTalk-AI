import type { ReactNode } from 'react';

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <img src="/sighttalk.svg" alt="" aria-hidden="true" />
          <strong>SightTalk AI</strong>
        </div>
        <span className="environment-badge">Local</span>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}
