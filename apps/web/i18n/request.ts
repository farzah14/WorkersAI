import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";
import idMessages from "@/messages/id.json";
import enMessages from "@/messages/en.json";

const messages = { id: idMessages, en: enMessages } as const;

export default getRequestConfig(async () => {
  const store = await cookies();
  const cookie = store.get("locale")?.value;
  const locale = cookie === "en" ? "en" : routing.defaultLocale;
  return {
    locale,
    messages: messages[locale],
  };
});