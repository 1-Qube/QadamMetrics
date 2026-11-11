import type { Metadata } from "next";
import "./globals.css";
import { AppProvider } from "@/context/AppContext";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

export const metadata: Metadata = {
  title: "QadamMetrics | Curriculum Intelligence Engine",
  description: "Turn assessment data into better teaching decisions with curriculum intelligence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#FAF9F6] text-[#151515] flex">
        <AppProvider>
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <TopBar />
            <main className="flex-1 p-8 overflow-y-auto">
              {children}
            </main>
          </div>
        </AppProvider>
      </body>
    </html>
  );
}
