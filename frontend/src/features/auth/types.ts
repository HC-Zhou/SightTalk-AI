export interface AuthCredentials {
  email: string;
  password: string;
}

export interface AuthUser {
  user_id: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  user: AuthUser;
  access_token: string;
  token_type: 'bearer';
  expires_at: string;
}
