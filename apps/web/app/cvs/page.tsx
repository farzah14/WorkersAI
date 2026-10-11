import { redirect } from "next/navigation";

export default async function CvsPage() {
  redirect("/dashboard/profile");
}
