import type { ConversationMessage } from '../session/types';

export interface ConversationArchive {
  id: string;
  title: string;
  createdAt: string;
  endedAt: string;
  messages: ConversationMessage[];
}

export interface ConversationArchiveResponse {
  id: string;
  title: string;
  created_at: string;
  ended_at: string;
  messages: ConversationMessage[];
}

export interface ConversationListResponse {
  conversations: ConversationArchiveResponse[];
}

export interface SaveConversationRequest {
  session_id: string;
  messages: ConversationMessage[];
}
