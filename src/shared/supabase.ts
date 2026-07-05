import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error("Missing Supabase environment variables. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.");
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
  realtime: {
    params: {
      eventsPerSecond: 10,
    },
  },
});

export type AppRole = "Admin" | "Viewer";

export type ProfileRow = {
  id: string;
  email: string;
  display_name: string | null;
  role: AppRole;
  org_id: string;
  super_admin: boolean;
  disabled: boolean;
  created_at: string | null;
  created_by: string | null;
  updated_at: string | null;
  updated_by: string | null;
};

export type BinRow = {
  id: string;
  org_id: string;
  bin_code: string;
  location: string | null;
  status: "Active" | "Maintenance" | "Inactive";
  capacity_liters: number | null;
  created_at: string | null;
  created_by: string | null;
  updated_at: string | null;
  updated_by: string | null;
};

export type PiDeviceRow = {
  id: string;
  bin_id: string;
  org_id: string;
  bin_code: string;
  device_name: string;
  token_hash: string;
  active: boolean;
  last_seen: string | null;
  created_at: string | null;
};

export type AdminMessageRow = {
  id: string;
  sender_id: string;
  sender_email: string;
  sender_org_id: string;
  recipient_id: string;
  recipient_email: string;
  recipient_org_id: string;
  subject: string;
  body: string;
  read_at: string | null;
  created_at: string | null;
};

export type OrgAnnouncementRow = {
  id: string;
  org_id: string | null;
  audience: "org" | "all";
  author_id: string;
  author_email: string;
  title: string;
  body: string;
  active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type AdminConversationRow = {
  id: string;
  org_admin_id: string;
  org_admin_email: string;
  org_id: string;
  super_admin_id: string;
  super_admin_email: string;
  created_at: string | null;
  updated_at: string | null;
};

export type AdminConversationMessageRow = {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_email: string;
  body: string;
  created_at: string | null;
};

export type AdminChatConversationRow = {
  id: string;
  org_id: string;
  participant_a_id: string;
  participant_a_email: string;
  participant_a_org_id: string;
  participant_a_super_admin: boolean;
  participant_b_id: string;
  participant_b_email: string;
  participant_b_org_id: string;
  participant_b_super_admin: boolean;
  created_by: string;
  created_at: string | null;
  updated_at: string | null;
};

export type AdminChatMessageRow = {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_email: string;
  body: string;
  created_at: string | null;
};
