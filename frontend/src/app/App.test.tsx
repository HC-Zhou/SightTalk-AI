import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '@/App';

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              status: 'ok',
              service: 'SightTalk AI API',
              version: '0.1.0',
              timestamp: new Date().toISOString(),
            }),
            {
              headers: {
                'Content-Type': 'application/json',
              },
            },
          ),
        );
      }),
    );
  });

  it('renders the application shell', async () => {
    render(<App />);

    expect(screen.getByText('SightTalk AI')).toBeInTheDocument();
    expect(await screen.findByText('API online')).toBeInTheDocument();
  });
});
