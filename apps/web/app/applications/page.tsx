import { redirect } from "next/navigation";

export default async function ApplicationsPage() {
  redirect("/dashboard/tracker");
}
