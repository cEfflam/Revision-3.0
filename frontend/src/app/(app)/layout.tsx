import { Sidebar } from "@/components/layout/nav";
import { UserProvider } from "@/components/layout/user-context";

/**
 * Gabarit de la zone connectée : garde d'authentification (UserProvider),
 * navigation, et une colonne de contenu centrée avec de l'air.
 * Le padding bas sur mobile évite que la barre d'onglets recouvre le contenu.
 */
export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <UserProvider>
      <Sidebar />
      <main className="min-h-screen px-4 pb-24 pt-6 md:ml-60 md:px-8 md:pb-10">
        <div className="mx-auto w-full max-w-3xl">{children}</div>
      </main>
    </UserProvider>
  );
}
