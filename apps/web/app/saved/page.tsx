import { redirect } from "next/navigation";

export default async function SavedJobsPage() {
  redirect("/dashboard/tracker");
}
