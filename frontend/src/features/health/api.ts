import { http } from '@/shared/api/http';

export interface HealthResponse {
  status: 'ok';
  service: string;
  version: string;
  timestamp: string;
}

export function getHealth() {
  return http<HealthResponse>('/health');
}
