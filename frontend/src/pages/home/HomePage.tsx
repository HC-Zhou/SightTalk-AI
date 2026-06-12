import { HealthPanel } from '@/features/health/HealthPanel';

export function HomePage() {
  return (
    <>
      <section className="page-heading">
        <h1>Operations workspace</h1>
        <p>Monitor service readiness and workflow activity from a single view.</p>
      </section>

      <section className="dashboard-grid" aria-label="Workspace overview">
        <HealthPanel />
        <article className="panel">
          <h3>Frontend</h3>
          <div className="metric">
            <strong>React</strong>
            <span>npm</span>
          </div>
          <p>Client workspace baseline is available.</p>
        </article>
        <article className="panel">
          <h3>Backend</h3>
          <div className="metric">
            <strong>3.14</strong>
            <span>Python</span>
          </div>
          <p>API service baseline is available.</p>
        </article>
      </section>
    </>
  );
}
