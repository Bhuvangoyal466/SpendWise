import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SpendWise AI",
  description: "Personal financial intelligence and decision-support platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
