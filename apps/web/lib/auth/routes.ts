const protectedPrefixes = [
  "/dashboard",
  "/cvs",
  "/jobs",
  "/exports",
  "/settings",
  "/find-jobs",
  "/onboarding",
  "/saved",
  "/applications",
];
export function requiresAuth(pathname: string): boolean {
  return protectedPrefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}