import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EZInvest — AI Investment Assistant",
  description: "Get fast, accurate investment advice powered by AI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
