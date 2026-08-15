import Link from "next/link";
import { signIn, signInWithGoogle } from "../actions";

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-2xl font-semibold">Sign in to Job Matcher</h1>
      {error && <p className="text-sm text-red-600">Sign-in failed. Please try again.</p>}
      <form action={signIn} className="flex w-full max-w-sm flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            name="email"
            type="email"
            required
            autoComplete="email"
            className="rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            name="password"
            type="password"
            required
            autoComplete="current-password"
            className="rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <button type="submit" className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700">
          Sign in
        </button>
      </form>
      <form action={signInWithGoogle}>
        <button type="submit" className="rounded border border-gray-300 px-4 py-2 hover:bg-gray-50">
          Continue with Google
        </button>
      </form>
      <p className="text-sm">
        No account yet?{" "}
        <Link href="/register" className="text-blue-600 underline">
          Register
        </Link>
      </p>
    </main>
  );
}