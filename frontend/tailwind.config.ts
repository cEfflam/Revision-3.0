import type { Config } from "tailwindcss";

/**
 * Design system REVISIO — Soft UI.
 *
 * La direction artistique tient en trois décisions :
 *   • fond gris froid très clair (#F8F9FC), cartes blanches très arrondies ;
 *   • un seul accent : l'indigo (boutons, barres, icônes actives) ;
 *   • ombres diffuses et faibles — le relief vient de la douceur, pas du
 *     contraste.
 * Tout le reste utilise la palette slate/indigo standard de Tailwind.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#F8F9FC",
      },
      borderRadius: {
        card: "28px",
        tile: "22px",
      },
      boxShadow: {
        soft: "0 8px 30px rgb(0 0 0 / 0.04)",
        "soft-lg": "0 12px 40px rgb(0 0 0 / 0.07)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
