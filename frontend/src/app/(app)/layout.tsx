import { MobileNav } from "@/components/shared/mobile-nav";
import { Sidebar } from "@/components/shared/sidebar";
import { Topbar } from "@/components/shared/topbar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen mesh-bg">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar />
        <main className="flex-1 overflow-x-hidden pb-20 lg:pb-0">{children}</main>
      </div>
      <MobileNav />
    </div>
  );
}
