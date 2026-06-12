import { useEffect, useState } from 'react';

import { getHealth, type HealthResponse } from '@/features/health/api';

type HealthState =
  | { status: 'loading' }
  | { status: 'ready'; data: HealthResponse }
  | { status: 'error'; message: string };

export function HealthPanel() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' });

  useEffect(() => {
    let isMounted = true;

    getHealth()
      .then((data) => {
        if (isMounted) {
          setHealth({ status: 'ready', data });
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          const message = error instanceof Error ? error.message : 'Backend unavailable';
          setHealth({ status: 'error', message });
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  if (health.status === 'loading') {
    return (
      <section className="panel" aria-live="polite">
        <h2>Backend health</h2>
        <div className="status-line">
          <span className="status-dot" />
          Checking API
        </div>
      </section>
    );
  }

  if (health.status === 'error') {
    return (
      <section className="panel" aria-live="polite">
        <h2>Backend health</h2>
        <div className="status-line">
          <span className="status-dot error" />
          API offline
        </div>
        <p className="muted">{health.message}</p>
      </section>
    );
  }

  return (
    <section className="panel" aria-live="polite">
      <h2>Backend health</h2>
      <div className="status-line">
        <span className="status-dot ok" />
        API online
      </div>
      <p className="muted">
        {health.data.service} · v{health.data.version}
      </p>
    </section>
  );
}
