import type { Metadata } from "next";
import localFont from "next/font/local";
import Script from "next/script";
import "./globals.css";
import Providers from "./providers";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "bahtzang.trader",
  description: "AI-powered trading dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-surface font-[family-name:var(--font-geist-sans)] antialiased`}
      >
        <Script id="theme-init" strategy="beforeInteractive">{
          `try{var t=localStorage.getItem("theme");if(t==="light")document.documentElement.classList.remove("dark");else document.documentElement.classList.add("dark")}catch(e){}`
        }</Script>
        <Script src="https://www.googletagmanager.com/gtag/js?id=G-P1W4024MVE" strategy="afterInteractive" />
        <Script id="gtag-init" strategy="afterInteractive">{
          `window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-P1W4024MVE');`
        }</Script>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
