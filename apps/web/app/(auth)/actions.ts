"use server";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export async function signIn(formData: FormData) {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) redirect("/login?error=invalid_credentials");
  redirect("/dashboard");
}

export async function signUp(formData: FormData) {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const confirmPassword = String(formData.get("confirmPassword") ?? "");
  if (password !== confirmPassword) redirect("/register?error=password_mismatch");
  const passwordRequirement = /^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;
  if (!passwordRequirement.test(password)) redirect("/register?error=weak_password");
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error?.code === "user_already_exists") redirect("/register?error=email_taken");
  if (error) redirect("/register?error=signup_failed");
  if (data?.session) redirect("/dashboard");
  redirect("/login?registered=1");
}

export async function signInWithGoogle() {
  const supabase = await createClient();
  const headerStore = await headers();
  const origin =
    headerStore.get("origin") ??
    process.env.NEXT_PUBLIC_APP_URL ??
    process.env.APP_URL ??
    "http://localhost:3000";
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: `${origin}/auth/callback` },
  });
  if (error || !data.url) redirect("/login?error=oauth_failed");
  redirect(data.url);
}

export async function requestPasswordReset(formData: FormData) {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "").trim();
  if (!email) redirect("/forgot-password?error=missing_email");

  const headerStore = await headers();
  const origin =
    headerStore.get("origin") ??
    process.env.NEXT_PUBLIC_APP_URL ??
    process.env.APP_URL ??
    "http://localhost:3000";

  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${origin}/auth/callback?next=/dashboard/settings`,
  });

  if (error) {
    if (error.status === 429) {
      redirect("/forgot-password?error=rate_limited");
    }
    redirect("/forgot-password?error=reset_failed");
  }

  redirect("/forgot-password?success=1");
}

export async function updatePassword(formData: FormData) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const password = String(formData.get("password") ?? "");
  const confirmPassword = String(formData.get("confirmPassword") ?? "");
  if (confirmPassword && password !== confirmPassword) {
    redirect("/dashboard/settings?error=password_mismatch");
  }

  const passwordRequirement = /^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;
  if (!passwordRequirement.test(password)) {
    redirect("/dashboard/settings?error=weak_password");
  }

  const { error } = await supabase.auth.updateUser({ password });
  if (error) {
    redirect("/dashboard/settings?error=update_password_failed");
  }

  redirect("/dashboard/settings?password_updated=1");
}