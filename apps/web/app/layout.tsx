import type { Metadata } from "next";
import { cookies } from "next/headers";
import { NextIntlClientProvider } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { Geist, Geist_Mono } from "next/font/google";
import { LocaleSwitcher } from "@/components/i18n/locale-switcher";
import { routing } from "@/i18n/routing";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Job Matcher",
  description: "AI Job Matcher",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const store = await cookies();
  const cookie = store.get("locale")?.value;
  const locale = cookie === "en" ? "en" : routing.defaultLocale;
  setRequestLocale(locale);

  return (
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <NextIntlClientProvider>
          <LocaleSwitcher locale={locale} />
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}