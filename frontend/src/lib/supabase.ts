import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

// Lazy singleton — avoids crashing at Next.js build time when env vars
// are not yet set.  The client is only created on first access in the browser.
let _client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!_client) {
    if (!supabaseUrl || !supabaseAnonKey) {
      throw new Error(
        "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set"
      );
    }
    _client = createClient(supabaseUrl, supabaseAnonKey);
  }
  return _client;
}
