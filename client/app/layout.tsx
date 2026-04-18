import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chatbot Trường Phổ thông Năng khiếu - ĐHQG-HCM",
  description: "Chatbot hỏi đáp thân thiện cho học sinh lớp 9 và phụ huynh về Trường Phổ thông Năng khiếu - ĐHQG-HCM.",
  icons: {
    icon: "/logo-ptnk.png",
    apple: "/logo-ptnk.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
